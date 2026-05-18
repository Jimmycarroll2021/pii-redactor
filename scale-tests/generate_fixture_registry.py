"""Generate a fixture registry for pii-redactor scale tests."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def counts(expected_rows: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in expected_rows:
        for label in row.get("labels", []):
            if label.get("valid", True):
                cat = label["category"]
                out[cat] = out.get(cat, 0) + 1
    return dict(sorted(out.items()))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures-dir", type=Path, default=Path("scale-tests/fixtures"))
    parser.add_argument("--out", type=Path, default=Path("scale-tests/fixtures/registry.json"))
    args = parser.parse_args()
    entries = []
    qwen_safe_names = {
        "pii-proof-20260503",
        "pii-context-proof-20260503",
        "pii-hidden-middle-40page-20260503",
        "kaggle-pii-diverse-12",
    }
    for fixture in sorted(args.fixtures_dir.iterdir()):
        if not fixture.is_dir():
            continue
        docs_path = fixture / "documents.jsonl"
        expected_path = fixture / "expected_labels.jsonl"
        if not docs_path.exists() or not expected_path.exists():
            continue
        docs = read_jsonl(docs_path)
        expected = read_jsonl(expected_path)
        name = fixture.name
        tier = "proof" if name.startswith("pii-") else "external" if any(key in name for key in ("kaggle", "ai4privacy", "gretel", "user")) else "scale"
        entries.append({
            "id": name,
            "tier": tier,
            "documents": str(docs_path).replace("\\", "/"),
            "expected": str(expected_path).replace("\\", "/"),
            "document_count": len(docs),
            "category_counts": counts(expected),
            "qwen_sample": name in qwen_safe_names,
            "required": True,
        })
    args.out.write_text(json.dumps({"fixtures": entries}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "OK", "fixtures": len(entries), "out": str(args.out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
