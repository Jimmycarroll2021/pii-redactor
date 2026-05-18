"""Production readiness gate for pii-redactor."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run_command(cmd: list[str], out_dir: Path, name: str) -> dict:
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    (out_dir / f"{name}.stdout.txt").write_text(proc.stdout, encoding="utf-8")
    (out_dir / f"{name}.stderr.txt").write_text(proc.stderr, encoding="utf-8")
    return {
        "name": name,
        "command": cmd,
        "returncode": proc.returncode,
        "status": "PASS" if proc.returncode == 0 else "FAIL",
    }


def load_registry(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["fixtures"]


def run_encrypted_audit(registry: Path, out_dir: Path) -> dict:
    audit_dir = out_dir / "encrypted-audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for fixture in load_registry(registry):
        run_dir = audit_dir / f"{fixture['id']}-mock-encrypted"
        cmd = [
            PYTHON,
            "scale-tests/run_library_benchmark.py",
            "--documents",
            fixture["documents"],
            "--expected",
            fixture["expected"],
            "--backend",
            "mock",
            "--audit-mode",
            "encrypted",
            "--out",
            str(run_dir),
        ]
        proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
        summary_path = run_dir / "summary.json"
        if not summary_path.exists():
            results.append(
                {
                    "fixture": fixture["id"],
                    "status": "FAIL",
                    "returncode": proc.returncode,
                    "error": proc.stderr[-2000:],
                }
            )
            continue
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        detected = sum(summary.get("detected_counts", {}).values())
        encrypted_ok = summary["audit"]["encrypted_value_count"] > 0 or detected == 0
        status = (
            "PASS"
            if summary.get("leak_count_total", 0) == 0
            and summary["audit"]["plaintext_leak_count"] == 0
            and encrypted_ok
            else "FAIL"
        )
        results.append(
            {
                "fixture": fixture["id"],
                "documents": summary["documents"],
                "output_leaks": summary.get("leak_count_total", 0),
                "audit_plaintext_leaks": summary["audit"]["plaintext_leak_count"],
                "audit_encrypted_values": summary["audit"]["encrypted_value_count"],
                "status": status,
            }
        )
    failed = [item for item in results if item["status"] != "PASS"]
    return {
        "name": "encrypted_audit",
        "status": "PASS" if not failed else "FAIL",
        "failed": len(failed),
        "documents": sum(item.get("documents", 0) for item in results),
        "results": results,
    }


def write_report(out_dir: Path, summary: dict) -> None:
    lines = [
        "# Production Gate Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Overall: `{summary['status']}`",
        f"Registry: `{summary['registry']}`",
        "",
        "| Check | Status | Details |",
        "|---|---|---|",
    ]
    for check in summary["checks"]:
        if check["name"] == "deterministic_registry":
            detail = check.get("run_dir", "")
        elif check["name"] == "encrypted_audit":
            detail = f"{check.get('documents', 0)} docs, {check.get('failed', 0)} failed"
        elif check["name"] == "ollama_quick":
            detail = check.get("run_dir", "")
        else:
            detail = f"returncode {check.get('returncode')}"
        lines.append(f"| `{check['name']}` | `{check['status']}` | {detail} |")
    (out_dir / "PRODUCTION-GATE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run production readiness gates.")
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("scale-tests/fixtures/registry-autonomous.json"),
    )
    parser.add_argument("--out", type=Path, default=Path("scale-tests/runs/production-gate"))
    parser.add_argument("--skip-encrypted-audit", action="store_true")
    parser.add_argument("--include-ollama", action="store_true")
    parser.add_argument("--ollama-model", default="qwen2.5:7b")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    checks = [
        run_command(
            [PYTHON, "-m", "compileall", "-q", "pii_redactor", "scale-tests"],
            args.out,
            "compileall",
        )
    ]

    deterministic_out = args.out / "deterministic-registry"
    deterministic = run_command(
        [
            PYTHON,
            "scale-tests/run_pii_eval_suite.py",
            "--profile",
            "full",
            "--backend",
            "mock",
            "--registry",
            str(args.registry),
            "--out",
            str(deterministic_out),
        ],
        args.out,
        "deterministic_registry",
    )
    deterministic["run_dir"] = str(deterministic_out)
    checks.append(deterministic)

    if not args.skip_encrypted_audit:
        checks.append(run_encrypted_audit(args.registry, args.out))

    if args.include_ollama:
        qwen_out = args.out / "ollama-quick"
        qwen = run_command(
            [
                PYTHON,
                "scale-tests/run_pii_eval_suite.py",
                "--profile",
                "quick",
                "--backend",
                "ollama",
                "--model",
                args.ollama_model,
                "--registry",
                str(args.registry),
                "--out",
                str(qwen_out),
            ],
            args.out,
            "ollama_quick",
        )
        qwen["run_dir"] = str(qwen_out)
        checks.append(qwen)

    failed = [check for check in checks if check["status"] != "PASS"]
    summary = {
        "status": "PASS" if not failed else "FAIL",
        "failed": len(failed),
        "registry": str(args.registry),
        "checks": checks,
    }
    (args.out / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_report(args.out, summary)
    evidence_proc = subprocess.run(
        [
            PYTHON,
            "-m",
            "pii_redactor.cli",
            "evidence",
            "--run",
            str(args.out),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    (args.out / "evidence.stdout.txt").write_text(evidence_proc.stdout, encoding="utf-8")
    (args.out / "evidence.stderr.txt").write_text(evidence_proc.stderr, encoding="utf-8")
    if evidence_proc.returncode != 0:
        checks.append(
            {
                "name": "evidence_pack",
                "command": [PYTHON, "-m", "pii_redactor.cli", "evidence", "--run", str(args.out)],
                "returncode": evidence_proc.returncode,
                "status": "FAIL",
            }
        )
        failed = [check for check in checks if check["status"] != "PASS"]
        summary = {
            "status": "FAIL",
            "failed": len(failed),
            "registry": str(args.registry),
            "checks": checks,
        }
        (args.out / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        write_report(args.out, summary)
    print(
        json.dumps(
            {"status": summary["status"], "failed": summary["failed"], "out": str(args.out)},
            sort_keys=True,
        )
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
