"""Command line interface for the PII Redactor KG/RAG firewall."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .config import Config
from .pipeline import build_pipeline
from .policies import (
    apply_policy_to_environment,
    available_policy_profiles,
    policy_snapshot,
)


TEXT_EXTENSIONS = {".txt", ".md", ".json", ".jsonl", ".csv", ".yaml", ".yml"}


def _iter_input_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return
    for item in sorted(path.rglob("*")):
        if item.is_file() and item.suffix.lower() in TEXT_EXTENSIONS:
            yield item


def _safe_read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _metadata_row(
    source_id: str,
    input_path: Path,
    output_path: Path,
    result,
    policy_name: str,
) -> dict:
    categories = sorted({span.category.value for span in result.spans})
    # Honest gate status: a document carrying fail-closed "suspected" redactions
    # (ID-shaped tokens that failed their checksum) must NOT report a clean pass.
    needs_review = bool(getattr(result, "needs_review", False))
    return {
        "source_id": source_id,
        "input_path": str(input_path),
        "output_path": str(output_path),
        "redaction_audit_id": result.audit_id,
        "pii_count": result.pii_count,
        "pii_categories": categories,
        "redaction_policy": policy_name,
        "model_used": result.model_used,
        "needs_review": needs_review,
        "gate_status": "review" if needs_review else "pass",
        "processed_at": result.processed_at.isoformat(),
    }


def _configure_policy(args: argparse.Namespace) -> str:
    profile = getattr(args, "policy", None) or os.environ.get(
        "PIIR_POLICY_PROFILE", "kg_rag_default"
    )
    os.environ["PIIR_POLICY_PROFILE"] = profile
    apply_policy_to_environment(profile, force=False)
    return profile


def cmd_redact(args: argparse.Namespace) -> int:
    policy_name = _configure_policy(args)
    pipeline = build_pipeline(Config.from_env())
    text = _safe_read_text(args.input)
    result = pipeline.process_document(text, document_id=args.document_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result.redacted_text, encoding="utf-8")
    metadata = _metadata_row(
        args.document_id or args.input.stem,
        args.input,
        args.output,
        result,
        policy_name,
    )
    if args.metadata:
        args.metadata.parent.mkdir(parents=True, exist_ok=True)
        args.metadata.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(metadata, sort_keys=True))
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    policy_name = _configure_policy(args)
    input_path = args.input.resolve()
    output_root = args.output.resolve()
    manifest_rows = []
    failures = []
    if not input_path.exists():
        failures.append({"input_path": str(input_path), "error": "Input path does not exist"})
        source_files = []
    else:
        source_files = list(_iter_input_files(input_path))
        if not source_files:
            failures.append({"input_path": str(input_path), "error": "Input path contains no supported text files"})
    pipeline = build_pipeline(Config.from_env()) if not failures else None
    for index, source_file in enumerate(source_files, start=1):
        relative = source_file.name if source_file.is_file() and input_path.is_file() else source_file.relative_to(input_path)
        output_path = output_root / relative
        source_id = f"{args.source_prefix}-{index:06d}"
        try:
            result = pipeline.process_document(_safe_read_text(source_file), document_id=source_id)  # type: ignore[union-attr]
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(result.redacted_text, encoding="utf-8")
            manifest_rows.append(
                _metadata_row(source_id, source_file, output_path, result, policy_name)
            )
        except Exception as exc:  # noqa: BLE001
            failures.append({"input_path": str(source_file), "error": str(exc)})
            if args.fail_fast:
                break
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    with args.manifest.open("w", encoding="utf-8") as handle:
        for row in manifest_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    review_rows = [r for r in manifest_rows if r.get("gate_status") == "review"]
    if failures or not manifest_rows:
        status = "FAIL"
    elif review_rows:
        status = "REVIEW"
    else:
        status = "PASS"
    summary = {
        "status": status,
        "policy": policy_name,
        "documents_processed": len(manifest_rows),
        "needs_review_documents": len(review_rows),
        "failures": failures,
        "manifest": str(args.manifest),
        "output": str(output_root),
    }
    print(json.dumps(summary, sort_keys=True))
    # Ingest is a transform step: hard failures exit non-zero; a REVIEW outcome
    # (suspected redactions present, but all redacted) still exits 0 so bulk
    # transforms complete — the enforcing `gate` command blocks on review.
    return 1 if status == "FAIL" else 0


def cmd_gate(args: argparse.Namespace) -> int:
    policy_name = _configure_policy(args)
    with tempfile.TemporaryDirectory(prefix="piir-gate-") as tmp:
        tmp_path = Path(tmp)
        ingest_args = argparse.Namespace(
            input=args.input,
            output=tmp_path / "redacted",
            manifest=tmp_path / "manifest.jsonl",
            policy=policy_name,
            source_prefix=args.source_prefix,
            fail_fast=True,
        )
        code = cmd_ingest(ingest_args)
        rows = []
        if ingest_args.manifest.exists():
            rows = [
                json.loads(line)
                for line in ingest_args.manifest.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        review_total = sum(1 for row in rows if row.get("gate_status") == "review")
        if code != 0:
            gate_state = "FAIL"
        elif review_total:
            # The gate is the enforcement point: suspected (failed-checksum)
            # redactions must be human-reviewed before the doc is cleared.
            gate_state = "REVIEW"
            code = 1
        else:
            gate_state = "PASS"
        summary = {
            "status": gate_state,
            "policy": policy_name,
            "documents_processed": len(rows),
            "needs_review_documents": review_total,
            "pii_count_total": sum(row["pii_count"] for row in rows),
            "pii_categories": sorted({cat for row in rows for cat in row["pii_categories"]}),
        }
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(summary, sort_keys=True))
        return code


def cmd_evidence(args: argparse.Namespace) -> int:
    run_dir = args.run.resolve()
    summary_path = run_dir / "summary.json"
    gate_summary_path = run_dir / "gate-summary.json"
    manifest_path = run_dir / "manifest.jsonl"
    summary_source = "summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    elif gate_summary_path.exists():
        summary = json.loads(gate_summary_path.read_text(encoding="utf-8"))
        summary_source = "gate-summary.json"
    elif manifest_path.exists():
        rows = [
            json.loads(line)
            for line in manifest_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        failed = [row for row in rows if row.get("gate_status") != "pass"]
        summary = {
            "status": "PASS" if not failed else "FAIL",
            "failed": len(failed),
            "documents_processed": len(rows),
            "pii_count_total": sum(row.get("pii_count", 0) for row in rows),
            "pii_categories": sorted({cat for row in rows for cat in row.get("pii_categories", [])}),
        }
        summary_source = "manifest.jsonl"
    else:
        raise FileNotFoundError(
            f"No supported evidence source found under {run_dir}; expected summary.json, gate-summary.json, or manifest.jsonl"
        )
    evidence = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(run_dir),
        "policy": policy_snapshot(args.policy),
        "summary": summary,
        "summary_source": summary_source,
    }
    json_path = run_dir / "evidence-summary.json"
    md_path = run_dir / "EVIDENCE-PACK.md"
    json_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# PII Firewall Evidence Pack",
                "",
                f"Generated: {evidence['generated_at']}",
                f"Run: `{run_dir}`",
                f"Policy: `{args.policy}`",
                f"Summary source: `{summary_source}`",
                f"Overall status: `{summary.get('status', 'UNKNOWN')}`",
                f"Failed checks: `{summary.get('failed', 'unknown')}`",
                "",
                "## Policy",
                "",
                f"- Description: {evidence['policy']['description']}",
                f"- Required metadata: {', '.join(evidence['policy']['required_metadata'])}",
                "",
                "## Source Files",
                "",
                f"- Machine-readable summary: `{json_path.name}`",
                f"- Evidence source: `{summary_source}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "PASS", "evidence": str(md_path), "summary": str(json_path)}, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PII Redactor KG/RAG firewall CLI.")
    parser.add_argument(
        "--policy",
        choices=available_policy_profiles(),
        default=os.environ.get("PIIR_POLICY_PROFILE", "kg_rag_default"),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    redact = sub.add_parser("redact", help="Redact one text file.")
    redact.add_argument("--input", type=Path, required=True)
    redact.add_argument("--output", type=Path, required=True)
    redact.add_argument("--metadata", type=Path)
    redact.add_argument("--document-id")
    redact.set_defaults(func=cmd_redact)

    ingest = sub.add_parser("ingest", help="Redact files into a KG/RAG-safe output directory.")
    ingest.add_argument("--input", type=Path, required=True)
    ingest.add_argument("--output", type=Path, required=True)
    ingest.add_argument("--manifest", type=Path, required=True)
    ingest.add_argument("--source-prefix", default="SRC")
    ingest.add_argument("--fail-fast", action="store_true")
    ingest.set_defaults(func=cmd_ingest)

    gate = sub.add_parser("gate", help="Fail/pass a file or folder through the PII firewall.")
    gate.add_argument("--input", type=Path, required=True)
    gate.add_argument("--output", type=Path)
    gate.add_argument("--source-prefix", default="GATE")
    gate.set_defaults(func=cmd_gate)

    evidence = sub.add_parser("evidence", help="Generate an evidence pack for a production gate run.")
    evidence.add_argument("--run", type=Path, required=True)
    evidence.set_defaults(func=cmd_evidence)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
