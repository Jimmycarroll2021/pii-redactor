"""Export reviewer-friendly de-PII calibration packs.

Produces:
- samples.jsonl: machine-readable review records
- REVIEW.md: human-readable checklist with redacted text, detected PII, expected labels,
  and reviewer fields for false positives / false negatives.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pii_redactor import Config, build_pipeline


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def expected_by_doc(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if "labels" in row:
            grouped[row["id"]].extend(row["labels"])
        else:
            grouped[row["document_id"]].append(row)
    return grouped


def main() -> int:
    parser = argparse.ArgumentParser(description="Export de-PII calibration review samples.")
    parser.add_argument("--documents", type=Path, required=True)
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--backend", choices=["mock", "ollama", "hf", "llama_cpp"], default="mock")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    docs = load_jsonl(args.documents)[: args.limit]
    expected = expected_by_doc(load_jsonl(args.expected))

    config = Config.from_env()
    config.backend = args.backend
    config.audit_enabled = False
    pipeline = build_pipeline(config)

    records: list[dict[str, Any]] = []
    for doc in docs:
        result = pipeline.process_document(doc["text"], document_id=doc["id"])
        records.append(
            {
                "document_id": doc["id"],
                "backend": args.backend,
                "model_used": result.model_used,
                "source_text": doc["text"],
                "redacted_text": result.redacted_text,
                "detected_pii_table": result.pii_table(),
                "expected_labels": expected.get(doc["id"], []),
                "review": {
                    "false_positives": [],
                    "false_negatives": [],
                    "notes": "",
                    "reviewer": "",
                    "reviewed_at": "",
                },
            }
        )

    with (args.out / "samples.jsonl").open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    lines = [
        "# De-PII Calibration Review Pack",
        "",
        f"Backend: `{args.backend}`",
        f"Documents: `{len(records)}`",
        "",
        "Reviewer instructions:",
        "",
        "- Add false positives: detected items that should not have been redacted.",
        "- Add false negatives: expected or visible sensitive values that were not redacted.",
        "- Do not paste real production PII into this file.",
        "",
    ]
    for index, record in enumerate(records, start=1):
        lines.extend(
            [
                f"## Sample {index}: {record['document_id']}",
                "",
                "### Redacted Text",
                "",
                "```text",
                record["redacted_text"],
                "```",
                "",
                "### Detected PII Table",
                "",
                "```json",
                json.dumps(record["detected_pii_table"], indent=2, sort_keys=True),
                "```",
                "",
                "### Expected Labels",
                "",
                "```json",
                json.dumps(record["expected_labels"], indent=2, sort_keys=True),
                "```",
                "",
                "### Reviewer Findings",
                "",
                "False positives:",
                "",
                "False negatives:",
                "",
                "Notes:",
                "",
            ]
        )
    (args.out / "REVIEW.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "OK", "documents": len(records), "out": str(args.out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
