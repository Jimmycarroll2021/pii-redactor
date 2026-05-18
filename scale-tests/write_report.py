from __future__ import annotations

import argparse
import json
from pathlib import Path


def fmt_rate(value: float) -> str:
    return f"{value:,.2f}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a Markdown benchmark report from summary.json.")
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    lines = [
        "# PII Redactor Scale-Test Report",
        "",
        f"Generated: {summary.get('generated_at', 'unknown')}",
        f"Status: {summary.get('status', 'unknown')}",
        "",
        "## Configuration",
        "",
        f"- Backend: {summary.get('backend', summary.get('url', 'unknown'))}",
        f"- Audit mode: {summary.get('audit_mode', 'n/a')}",
        f"- Documents: {summary.get('documents', summary.get('documents_input', 'n/a'))}",
        "",
        "## Throughput",
        "",
        f"- Total seconds: {summary.get('total_seconds', 0):.4f}",
        f"- Docs/sec: {fmt_rate(summary.get('docs_per_second', 0.0))}",
        f"- Estimated docs/day: {fmt_rate(summary.get('estimated_docs_per_day', 0.0))}",
        "",
        "## Latency",
        "",
    ]

    latency = summary.get("latency_ms") or summary.get("batch_latency_ms") or {}
    for key in ["min", "mean", "median", "p95", "max"]:
        lines.append(f"- {key}: {latency.get(key, 0):.4f} ms")

    lines.extend(["", "## Correctness Signals", ""])
    if "expected_valid_counts" in summary:
        lines.append("Expected valid labels:")
        for category, count in summary.get("expected_valid_counts", {}).items():
            lines.append(f"- {category}: {count}")
        lines.append("")
    if "detected_counts" in summary:
        lines.append("Detected labels:")
        for category, count in summary.get("detected_counts", {}).items():
            lines.append(f"- {category}: {count}")
        lines.append("")

    lines.extend(["## Privacy Safety", ""])
    lines.append(f"- Leak checked total: {sum(summary.get('leak_checked_counts', {}).values())}")
    lines.append(f"- Leak count total: {summary.get('leak_count_total', 0)}")
    for category, count in summary.get("leak_counts", {}).items():
        lines.append(f"- {category}: {count}")
    if summary.get("leak_check_scope"):
        lines.extend(["", f"Scope note: {summary['leak_check_scope']}"])

    lines.extend([
        "",
        "## Limitations",
        "",
        "- Synthetic data proves repeatability and pipeline behavior, not real-world clinical recall.",
        "- Mock backend measurements isolate deterministic regex and local pipeline overhead.",
        "- Service-backed benchmarks should be run separately with the target local LLM backend and deployment hardware.",
        "",
    ])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(str(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
