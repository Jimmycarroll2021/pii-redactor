"""Convert user-supplied PII ZIP datasets into pii-redactor benchmark fixtures."""
from __future__ import annotations

import argparse
import ast
import csv
import io
import json
import zipfile
from pathlib import Path
from typing import Any

LABEL_MAP = {
    "NAME_STUDENT": "name",
    "NAME": "name",
    "GIVENNAME": "name",
    "SURNAME": "name",
    "FIRSTNAME": "name",
    "LASTNAME": "name",
    "EMAIL": "email",
    "EMAIL_ADDRESS": "email",
    "PHONE": "phone",
    "PHONE_NUM": "phone",
    "PHONE_NUMBER": "phone",
    "ADDRESS": "address",
    "STREET_ADDRESS": "address",
    "CITY": "address",
    "STREET": "address",
    "ZIPCODE": "address",
    "URL": "url",
    "URL_PERSONAL": "url",
    "USERNAME": "username",
    "USER_NAME": "username",
    "ID": "generic_id",
    "ID_NUM": "generic_id",
    "SSN": "generic_id",
    "CREDIT_CARD": "generic_id",
    "DATE": "date",
    "TIME": "date",
}


def _is_valid_label(category: str, value: str) -> bool:
    stripped = value.strip()
    if category == "email":
        return "@" in stripped and "." in stripped.rsplit("@", 1)[-1]
    if category == "phone":
        return sum(ch.isdigit() for ch in stripped) >= 7
    if category == "generic_id":
        return len(stripped) >= 3 and not stripped.isalpha()
    if category == "url":
        return "." in stripped or "/" in stripped
    if category == "username":
        if len(stripped) < 5 or len(stripped) > 32:
            return False
        if any(ch.isspace() for ch in stripped):
            return False
        if "'" in stripped:
            return False
        if stripped.isalpha():
            return False
    return True


def write_fixture(rows: list[dict[str, Any]], out: Path, source: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    docs = []
    expected = []
    counts: dict[str, int] = {}
    for row in rows:
        docs.append({"id": row["id"], "text": row["text"]})
        labels = []
        seen = set()
        for label in row["labels"]:
            value = str(label.get("value", "")).strip()
            category = str(label.get("category", "")).strip()
            if not value or not category:
                continue
            key = (category, value)
            if key in seen:
                continue
            seen.add(key)
            labels.append({"category": category, "valid": _is_valid_label(category, value), "value": value})
            counts[category] = counts.get(category, 0) + 1
        expected.append({"id": row["id"], "labels": labels})
    (out / "documents.jsonl").write_text("".join(json.dumps(d, sort_keys=True) + "\n" for d in docs), encoding="utf-8")
    (out / "expected_labels.jsonl").write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in expected), encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps({"source": source, "documents": len(docs), "label_counts": counts}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "OK", "out": str(out), "documents": len(docs), "label_counts": counts}, sort_keys=True))


def csv_rows(zip_path: Path, out: Path, limit: int) -> None:
    rows = []
    with zipfile.ZipFile(zip_path) as zf:
        csv_name = next(name for name in zf.namelist() if name.endswith(".csv"))
        with zf.open(csv_name) as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", newline=""))
            for idx, src in enumerate(reader, start=1):
                labels = []
                for column, category in {
                    "name": "name",
                    "email": "email",
                    "phone": "phone",
                    "address": "address",
                    "username": "username",
                    "url": "url",
                }.items():
                    value = (src.get(column) or "").strip()
                    if value:
                        labels.append({"category": category, "value": value})
                rows.append({"id": f"usercsv-{src.get('document') or idx}", "text": src.get("text", ""), "labels": labels})
                if limit and len(rows) >= limit:
                    break
    write_fixture(rows, out, str(zip_path))


def openpii_rows(zip_path: Path, out: Path, entry: str, limit: int, languages: set[str] | None) -> None:
    rows = []
    entry = entry.replace("\\", "/")
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open(entry) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8")
            for line in text:
                if not line.strip():
                    continue
                src = json.loads(line)
                if languages and src.get("language") not in languages:
                    continue
                labels = []
                privacy_mask = src.get("privacy_mask") or []
                if isinstance(privacy_mask, str):
                    privacy_mask = ast.literal_eval(privacy_mask)
                for item in privacy_mask:
                    mapped = LABEL_MAP.get(str(item.get("label", "")).upper())
                    if mapped:
                        labels.append({"category": mapped, "value": str(item.get("value", ""))})
                if labels:
                    rows.append({"id": f"useropenpii-{src.get('uid')}", "text": src.get("source_text", ""), "labels": labels})
                if limit and len(rows) >= limit:
                    break
    write_fixture(rows, out, f"{zip_path}:{entry}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=["csv", "openpii"], required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--entry", default="data/validation/test.jsonl")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--languages", default="en")
    args = parser.parse_args()
    if args.kind == "csv":
        csv_rows(args.zip, args.out, args.limit)
    else:
        languages = {item.strip() for item in args.languages.split(",") if item.strip()} if args.languages else None
        openpii_rows(args.zip, args.out, args.entry, args.limit, languages)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
