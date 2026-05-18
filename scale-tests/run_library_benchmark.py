from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pii_redactor.config import Config
from pii_redactor.pipeline import build_pipeline

MOCK_LLM_EXCLUDED_LEAK_CATEGORIES = {"name", "address", "date_of_birth"}


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return ordered[index]


def category_counts(expected_rows: list[dict], valid_only: bool = True) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in expected_rows:
        for item in row.get("labels", []):
            if valid_only and not item.get("valid", True):
                continue
            counts[item["category"]] += 1
    return counts


def should_check_leak(item: dict, backend: str) -> bool:
    if not item.get("valid", True):
        return False
    if backend == "mock" and item.get("category") in MOCK_LLM_EXCLUDED_LEAK_CATEGORIES:
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark the PII redactor library pipeline over a JSONL corpus.")
    parser.add_argument("--documents", type=Path, required=True)
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--backend", choices=["mock", "ollama", "hf", "llama_cpp"], default="mock")
    parser.add_argument("--audit-mode", choices=["disabled", "metadata", "encrypted"], default="disabled")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--disable-regex-prepass", action="store_true")
    args = parser.parse_args()

    docs = read_jsonl(args.documents)
    expected_rows = read_jsonl(args.expected)
    expected_by_id = {row["id"]: row for row in expected_rows}
    if args.limit:
        docs = docs[: args.limit]

    args.out.mkdir(parents=True, exist_ok=True)

    audit_path = args.out / "audit.jsonl"
    audit_key = None
    if args.audit_mode == "encrypted":
        from cryptography.fernet import Fernet

        audit_key = Fernet.generate_key().decode("ascii")

    config = Config.from_env()
    config.backend = args.backend
    config.audit_enabled = args.audit_mode != "disabled"
    config.audit_log_path = str(audit_path)
    config.audit_encryption_key = audit_key
    pipeline = build_pipeline(config, use_regex_prepass=not args.disable_regex_prepass)

    latencies_ms: list[float] = []
    detected_counts: Counter[str] = Counter()
    leak_counts: Counter[str] = Counter()
    checked_counts: Counter[str] = Counter()
    result_rows: list[dict] = []

    started = time.perf_counter()
    for doc in docs:
        item_started = time.perf_counter()
        result = pipeline.process_document(doc["text"], document_id=doc["id"])
        elapsed_ms = (time.perf_counter() - item_started) * 1000.0
        latencies_ms.append(elapsed_ms)

        safe_payload = result.to_dict()
        safe_payload.pop("processed_at", None)
        safe_text = json.dumps(safe_payload, sort_keys=True)
        for detection in result.spans:
            detected_counts[detection.category.value] += 1

        expected = expected_by_id.get(doc["id"], {"labels": []})
        leaks: list[dict] = []
        for label in expected.get("labels", []):
            if should_check_leak(label, args.backend):
                checked_counts[label["category"]] += 1
                if label["value"] in safe_text:
                    leaks.append(label)
                    leak_counts[label["category"]] += 1

        result_rows.append(
            {
                "id": doc["id"],
                "processing_ms": elapsed_ms,
                "detections": len(result.spans),
                "leaks": leaks,
                "pii_table_rows": len(result.pii_table()),
            }
        )

    total_seconds = time.perf_counter() - started
    docs_processed = len(docs)
    docs_per_second = docs_processed / total_seconds if total_seconds else 0.0
    audit_text = audit_path.read_text(encoding="utf-8") if audit_path.exists() else ""
    audit_lines = [line for line in audit_text.splitlines() if line.strip()]
    audit_encrypted_value_count = 0
    for line in audit_lines:
        try:
            if json.loads(line).get("value_encrypted"):
                audit_encrypted_value_count += 1
        except json.JSONDecodeError:
            continue

    audit_plaintext_leak_count = 0
    if audit_text:
        audit_metadata_text_parts: list[str] = []
        excluded_audit_fields = {"audit_id", "timestamp", "value_encrypted"}
        for line in audit_lines:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                audit_metadata_text_parts.append(line)
                continue
            safe_entry = {k: v for k, v in entry.items() if k not in excluded_audit_fields}
            audit_metadata_text_parts.append(json.dumps(safe_entry, sort_keys=True))
        audit_metadata_text = "\n".join(audit_metadata_text_parts)
        for doc in docs:
            expected = expected_by_id.get(doc["id"], {"labels": []})
            for label in expected.get("labels", []):
                if should_check_leak(label, args.backend) and label["value"] in audit_metadata_text:
                    audit_plaintext_leak_count += 1

    summary = {
        "status": "OK",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "backend": args.backend,
        "regex_prepass": not args.disable_regex_prepass,
        "audit_mode": args.audit_mode,
        "audit": {
            "enabled": args.audit_mode != "disabled",
            "path": str(audit_path) if args.audit_mode != "disabled" else None,
            "log_exists": audit_path.exists(),
            "line_count": len(audit_lines),
            "encrypted_value_count": audit_encrypted_value_count,
            "plaintext_leak_count": audit_plaintext_leak_count,
            "encryption_key_generated": bool(audit_key),
        },
        "documents": docs_processed,
        "total_seconds": total_seconds,
        "docs_per_second": docs_per_second,
        "estimated_docs_per_day": docs_per_second * 86400.0,
        "latency_ms": {
            "min": min(latencies_ms) if latencies_ms else 0.0,
            "mean": statistics.mean(latencies_ms) if latencies_ms else 0.0,
            "median": statistics.median(latencies_ms) if latencies_ms else 0.0,
            "p95": percentile(latencies_ms, 95),
            "max": max(latencies_ms) if latencies_ms else 0.0,
        },
        "expected_valid_counts": dict(sorted(category_counts(expected_rows).items())),
        "detected_counts": dict(sorted(detected_counts.items())),
        "leak_checked_counts": dict(sorted(checked_counts.items())),
        "leak_counts": dict(sorted(leak_counts.items())),
        "leak_count_total": sum(leak_counts.values()),
        "missed_counts": dict(sorted(leak_counts.items())),
        "missed_count_total": sum(leak_counts.values()),
        "leak_check_scope": "Mock backend excludes name, address, and date_of_birth because those require LLM extraction; structured values remain checked.",
        "inputs": {"documents": str(args.documents), "expected": str(args.expected)},
    }

    with (args.out / "results.jsonl").open("w", encoding="utf-8") as handle:
        for row in result_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
