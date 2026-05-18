"""Convert Kaggle PII Detection JSON into pii-redactor benchmark JSONL.

Input schema is the Kaggle competition-style list of records with:
- document
- full_text
- tokens
- trailing_whitespace
- labels

Output schema:
- documents.jsonl: {id, text}
- expected_labels.jsonl: {id, labels:[{category,value,valid}]}
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

LABEL_MAP = {
    "NAME_STUDENT": "name",
    "EMAIL": "email",
    "PHONE_NUM": "phone",
    "STREET_ADDRESS": "address",
    "URL_PERSONAL": "url",
    "ID_NUM": "generic_id",
    "USERNAME": "username",
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


def normalise_label(label: str) -> str:
    if label == "O":
        return "O"
    if "-" in label:
        return label.split("-", 1)[1]
    return label


def token_text(tokens: list[str], trailing: list[bool], start: int, end: int) -> str:
    parts: list[str] = []
    for i in range(start, end):
        parts.append(tokens[i])
        if i < end - 1 and trailing[i]:
            parts.append(" ")
    return "".join(parts).strip()


def extract_labels(row: dict) -> list[dict]:
    tokens = row["tokens"]
    trailing = row["trailing_whitespace"]
    labels = row["labels"]
    found: list[dict] = []
    i = 0
    while i < len(labels):
        raw = labels[i]
        kind = normalise_label(raw)
        if kind == "O" or kind not in LABEL_MAP:
            i += 1
            continue
        start = i
        i += 1
        while i < len(labels) and normalise_label(labels[i]) == kind and labels[i].startswith("I-"):
            i += 1
        value = token_text(tokens, trailing, start, i)
        if value:
            found.append({"category": LABEL_MAP[kind], "valid": _is_valid_label(LABEL_MAP[kind], value), "value": value})
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--only-with-pii", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    rows = json.loads(args.input.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)

    docs = []
    expected = []
    for row in rows:
        labels = extract_labels(row)
        if args.only_with_pii and not labels:
            continue
        doc_id = f"kaggle-{row['document']}"
        docs.append({"id": doc_id, "text": row["full_text"]})
        expected.append({"id": doc_id, "labels": labels})
        if args.limit and len(docs) >= args.limit:
            break

    with (args.out / "documents.jsonl").open("w", encoding="utf-8") as handle:
        for row in docs:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    with (args.out / "expected_labels.jsonl").open("w", encoding="utf-8") as handle:
        for row in expected:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    counts: dict[str, int] = {}
    for row in expected:
        for label in row["labels"]:
            counts[label["category"]] = counts.get(label["category"], 0) + 1

    print(json.dumps({"status": "OK", "documents": len(docs), "label_counts": counts, "out": str(args.out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
