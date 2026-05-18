"""Prepare downloaded Kaggle PII datasets as pii-redactor fixtures.

Expected input root:
    scale-tests/external/kaggle-complete

This script assumes archives have already been downloaded and unzipped by the
Kaggle CLI. It converts supported datasets into the standard fixture shape:

    documents.jsonl
    expected_labels.jsonl

It also writes a registry containing only the generated Kaggle-complete
fixtures, so they can be gated separately from the existing autonomous suite.
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


FIXTURE_SPECS = [
    {
        "id": "kaggle-complete-openpii-500k-train-all",
        "kind": "openpii_zip",
        "zip": "open-pii-masking-500k-ai4privacy/open-pii-masking-500k-ai4privacy.zip",
        "entry": "data/train/train.jsonl",
        "languages": "",
    },
    {
        "id": "kaggle-complete-openpii-500k-validation-all",
        "kind": "openpii_zip",
        "zip": "open-pii-masking-500k-ai4privacy/open-pii-masking-500k-ai4privacy.zip",
        "entry": "data/validation/test.jsonl",
        "languages": "",
    },
    {
        "id": "kaggle-complete-crapii-cleaned-repository",
        "kind": "kaggle_json",
        "input": "crapii-cleaned-repository/cleaned-repository-of-annotated-pii/cleaned_repository_pii_train.json",
    },
    {
        "id": "kaggle-complete-persuade-pii",
        "kind": "kaggle_json",
        "input": "persuade-pii-dataset/persuade-pii-dataset/persuade_train_v0.json",
    },
    {
        "id": "kaggle-complete-mistral-generated",
        "kind": "kaggle_json",
        "input": "pii-dd-mistral-generated/pii-dd-mistral-generated/mixtral-8x7b-v1.json",
    },
    {
        "id": "kaggle-complete-pii-external-csv",
        "kind": "csv_zip",
        "zip": "pii-external-dataset/pii-external-dataset.zip",
    },
    {
        "id": "kaggle-complete-ai4privacy-en-8k",
        "kind": "ai4privacy_jsonl",
        "input": "ai4privacy-en-38k/ai-4-privacy-pii-masking-en-38k/1english_openpii_8k.jsonl",
    },
    {
        "id": "kaggle-complete-ai4privacy-en-30k",
        "kind": "ai4privacy_jsonl",
        "input": "ai4privacy-en-38k/ai-4-privacy-pii-masking-en-38k/1english_openpii_30k.jsonl",
    },
]


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True)


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def count_labels(expected_path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in read_jsonl(expected_path):
        for label in row.get("labels", []):
            if label.get("valid", True):
                category = label["category"]
                counts[category] = counts.get(category, 0) + 1
    return dict(sorted(counts.items()))


def write_registry(fixture_ids: list[str], fixtures_dir: Path, out: Path) -> None:
    entries = []
    for fixture_id in fixture_ids:
        fixture = fixtures_dir / fixture_id
        docs_path = fixture / "documents.jsonl"
        expected_path = fixture / "expected_labels.jsonl"
        docs = read_jsonl(docs_path)
        entries.append(
            {
                "id": fixture_id,
                "tier": "external",
                "documents": str(docs_path).replace("\\", "/"),
                "expected": str(expected_path).replace("\\", "/"),
                "document_count": len(docs),
                "category_counts": count_labels(expected_path),
                "qwen_sample": False,
                "required": True,
            }
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"fixtures": entries}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_manifest(root: Path, fixtures_dir: Path, registry: Path, results: list[dict]) -> None:
    (root / "conversion-results.json").write_text(
        json.dumps(
            {
                "fixtures_dir": str(fixtures_dir),
                "registry": str(registry),
                "results": results,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--external-root", type=Path, default=Path("scale-tests/external/kaggle-complete"))
    parser.add_argument("--fixtures-dir", type=Path, default=Path("scale-tests/fixtures"))
    parser.add_argument("--registry", type=Path, default=Path("scale-tests/fixtures/registry-kaggle-complete.json"))
    args = parser.parse_args()

    fixture_ids = []
    results = []
    for spec in FIXTURE_SPECS:
        fixture_id = spec["id"]
        out_dir = args.fixtures_dir / fixture_id
        fixture_ids.append(fixture_id)
        if spec["kind"] == "openpii_zip":
            cmd = [
                PYTHON,
                "scale-tests/convert_user_supplied_pii.py",
                "--kind",
                "openpii",
                "--zip",
                str(args.external_root / spec["zip"]),
                "--entry",
                spec["entry"],
                "--languages",
                spec["languages"],
                "--limit",
                "0",
                "--out",
                str(out_dir),
            ]
        elif spec["kind"] == "kaggle_json":
            cmd = [
                PYTHON,
                "scale-tests/convert_kaggle_pii.py",
                "--input",
                str(args.external_root / spec["input"]),
                "--out",
                str(out_dir),
                "--only-with-pii",
            ]
        elif spec["kind"] == "csv_zip":
            cmd = [
                PYTHON,
                "scale-tests/convert_user_supplied_pii.py",
                "--kind",
                "csv",
                "--zip",
                str(args.external_root / spec["zip"]),
                "--limit",
                "0",
                "--out",
                str(out_dir),
            ]
        elif spec["kind"] == "ai4privacy_jsonl":
            cmd = [
                PYTHON,
                "scale-tests/convert_public_pii_datasets.py",
                "--source",
                "ai4privacy",
                "--input",
                str(args.external_root / spec["input"]),
                "--limit",
                "0",
                "--out",
                str(out_dir),
            ]
        else:
            raise ValueError(f"Unsupported fixture kind: {spec['kind']}")
        run(cmd)
        docs_path = out_dir / "documents.jsonl"
        expected_path = out_dir / "expected_labels.jsonl"
        results.append(
            {
                "id": fixture_id,
                "documents": len(read_jsonl(docs_path)),
                "category_counts": count_labels(expected_path),
            }
        )

    write_registry(fixture_ids, args.fixtures_dir, args.registry)
    write_manifest(args.external_root, args.fixtures_dir, args.registry, results)
    print(
        json.dumps(
            {
                "status": "OK",
                "fixtures": len(fixture_ids),
                "registry": str(args.registry),
                "documents": sum(item["documents"] for item in results),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
