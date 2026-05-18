"""Convert public synthetic PII datasets into pii-redactor benchmark fixtures."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

import pandas as pd

LABEL_MAP = {
    "USERNAME": "username",
    "USER_NAME": "username",
    "user_name": "username",
    "GIVENNAME": "name",
    "SURNAME": "name",
    "FIRSTNAME": "name",
    "LASTNAME": "name",
    "EMAIL": "email",
    "email": "email",
    "EMAIL_ADDRESS": "email",
    "PHONE": "phone",
    "PHONE_NUMBER": "phone",
    "phone_number": "phone",
    "ADDRESS": "address",
    "STREET_ADDRESS": "address",
    "address": "address",
    "PERSON": "name",
    "PERSON_NAME": "name",
    "FULL_NAME": "name",
    "NAME": "name",
    "name": "name",
    "DATE_OF_BIRTH": "date_of_birth",
    "DOB": "date_of_birth",
    "BIRTHDATE": "date_of_birth",
    "URL": "url",
    "IP_ADDRESS": "ip_address",
    "CREDIT_CARD": "generic_id",
    "SSN": "generic_id",
    "ID": "generic_id",
    "ID_NUM": "generic_id",
    "ACCOUNT_NUMBER": "generic_id",
    "CITY": "address",
    "STREET": "address",
    "ZIPCODE": "address",
    "POSTCODE": "address",
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


def write_fixture(rows: list[dict[str, Any]], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    docs = []
    expected = []
    for row in rows:
        docs.append({"id": row["id"], "text": row["text"]})
        labels = []
        seen = set()
        for label in row["labels"]:
            key = (label["category"], label["value"])
            if key in seen or not label["value"]:
                continue
            seen.add(key)
            labels.append({"category": label["category"], "valid": _is_valid_label(label["category"], label["value"]), "value": label["value"]})
        expected.append({"id": row["id"], "labels": labels})
    (out / "documents.jsonl").write_text("".join(json.dumps(d, sort_keys=True) + "\n" for d in docs), encoding="utf-8")
    (out / "expected_labels.jsonl").write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in expected), encoding="utf-8")
    counts: dict[str, int] = {}
    for e in expected:
        for label in e["labels"]:
            counts[label["category"]] = counts.get(label["category"], 0) + 1
    print(json.dumps({"status": "OK", "out": str(out), "documents": len(docs), "label_counts": counts}, sort_keys=True))


def convert_ai4privacy(input_path: Path, out: Path, limit: int) -> None:
    rows = []
    with input_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            src = json.loads(line)
            labels = []
            for item in src.get("privacy_mask", []):
                mapped = LABEL_MAP.get(str(item.get("label", "")))
                if mapped:
                    labels.append({"category": mapped, "value": str(item.get("value", ""))})
            if labels:
                rows.append({"id": f"ai4privacy-{src.get('id')}", "text": src["source_text"], "labels": labels})
            if limit and len(rows) >= limit:
                break
    write_fixture(rows, out)


def convert_gretel(input_path: Path, out: Path, limit: int) -> None:
    df = pd.read_parquet(input_path)
    rows = []
    for _, src in df.iterrows():
        labels = []
        entities = ast.literal_eval(src["entities"])
        for entity in entities:
            value = str(entity.get("entity", ""))
            for typ in entity.get("types", []):
                mapped = LABEL_MAP.get(str(typ)) or LABEL_MAP.get(str(typ).upper())
                if mapped:
                    labels.append({"category": mapped, "value": value})
                    break
        if labels:
            rows.append({"id": f"gretel-{src['uid']}", "text": src["text"], "labels": labels})
        if limit and len(rows) >= limit:
            break
    write_fixture(rows, out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["ai4privacy", "gretel"], required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    if args.source == "ai4privacy":
        convert_ai4privacy(args.input, args.out, args.limit)
    else:
        convert_gretel(args.input, args.out, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
