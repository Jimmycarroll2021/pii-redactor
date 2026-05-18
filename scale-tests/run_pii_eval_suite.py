"""Run the consolidated PII eval suite."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def load_registry(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["fixtures"]


def run_one(fixture: dict, backend: str, out_dir: Path, limit: int = 0) -> dict:
    run_dir = out_dir / f"{fixture['id']}-{backend}"
    cmd = [
        PYTHON,
        "scale-tests/run_library_benchmark.py",
        "--documents", fixture["documents"],
        "--expected", fixture["expected"],
        "--backend", backend,
        "--audit-mode", "disabled",
        "--out", str(run_dir),
    ]
    if limit:
        cmd.extend(["--limit", str(limit)])
    env = os.environ.copy()
    if backend == "ollama":
        env.setdefault("PIIR_OLLAMA_MODEL", "qwen2.5:7b")
        env.setdefault("PIIR_OLLAMA_URL", "http://127.0.0.1:11434")
        env.setdefault("PIIR_LLM_TIMEOUT_SECONDS", "600")
        env.setdefault("PIIR_LLM_RETRIES", "1")
    proc = subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True)
    summary_path = run_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {
        "status": "ERROR",
        "leak_count_total": 999999,
        "error": proc.stderr[-2000:],
    }
    return {
        "fixture": fixture["id"],
        "backend": backend,
        "run_dir": str(run_dir).replace("\\", "/"),
        "exit_code": proc.returncode,
        "documents": summary.get("documents", 0),
        "leaks": summary.get("leak_count_total", 0),
        "leak_counts": summary.get("leak_counts", {}),
        "status": "PASS" if proc.returncode == 0 and summary.get("leak_count_total", 0) == 0 else "FAIL",
    }


def select_fixtures(fixtures: list[dict], profile: str) -> list[dict]:
    if profile == "quick":
        wanted = {"pii-proof-20260503", "pii-context-proof-20260503", "pii-hidden-middle-40page-20260503", "kaggle-pii-diverse-12"}
        return [f for f in fixtures if f["id"] in wanted]
    if profile == "proper":
        return [f for f in fixtures if f.get("required", True)]
    return fixtures


def write_report(out_dir: Path, results: list[dict], profile: str) -> None:
    failed = [r for r in results if r["status"] != "PASS"]
    lines = [
        "# PII Eval Suite Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Profile: `{profile}`",
        f"Overall: `{'FAIL' if failed else 'PASS'}`",
        "",
        "| Fixture | Backend | Docs | Leaks | Status |",
        "|---|---|---:|---:|---|",
    ]
    for r in results:
        lines.append(f"| {r['fixture']} | {r['backend']} | {r['documents']} | {r['leaks']} | {r['status']} |")
    lines.extend(["", "## Failed Runs", ""])
    if not failed:
        lines.append("None.")
    for r in failed:
        lines.append(f"- `{r['fixture']}` / `{r['backend']}`: {r['leaks']} leaks, run `{r['run_dir']}`")
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run consolidated PII eval suite.")
    parser.add_argument("--profile", choices=["quick", "proper", "full"], default="proper")
    parser.add_argument("--registry", type=Path, default=Path("scale-tests/fixtures/registry.json"))
    parser.add_argument("--backend", choices=["mock", "ollama"], default="mock")
    parser.add_argument("--model", default="qwen2.5:7b")
    parser.add_argument("--qwen-sample-limit", type=int, default=3)
    parser.add_argument("--out", type=Path, default=Path(""))
    args = parser.parse_args()

    fixtures = select_fixtures(load_registry(args.registry), args.profile)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_dir = args.out or Path("scale-tests/runs") / f"{stamp}-pii-eval-{args.profile}"
    out_dir.mkdir(parents=True, exist_ok=True)

    os.environ["PIIR_OLLAMA_MODEL"] = args.model
    results = []
    for fixture in fixtures:
        results.append(run_one(fixture, "mock", out_dir))
    if args.backend == "ollama":
        for fixture in fixtures:
            if fixture.get("qwen_sample"):
                results.append(run_one(fixture, "ollama", out_dir, limit=args.qwen_sample_limit))

    failed = [r for r in results if r["status"] != "PASS"]
    (out_dir / "summary.json").write_text(json.dumps({"profile": args.profile, "results": results, "failed": len(failed)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "results.jsonl").open("w", encoding="utf-8") as handle:
        for row in results:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    write_report(out_dir, results, args.profile)
    print(json.dumps({"status": "FAIL" if failed else "PASS", "failed": len(failed), "out": str(out_dir)}, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
