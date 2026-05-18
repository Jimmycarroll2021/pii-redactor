from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

FIRST_NAMES = ["Ava", "Noah", "Mia", "Oliver", "Isla", "Jack", "Grace", "Leo", "Zoe", "Henry"]
LAST_NAMES = ["Nguyen", "Smith", "Patel", "Brown", "Wilson", "Taylor", "Singh", "Martin", "O'Connor", "Lee"]
STREETS = ["King Street", "George Street", "Collins Street", "Queen Street", "Elizabeth Street"]
SUBURBS = ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"]

CATEGORY_KEYS = [
    "name",
    "date_of_birth",
    "address",
    "email",
    "phone",
    "tfn",
    "abn",
    "acn",
    "medicare",
    "driver_licence",
    "passport",
    "crn",
    "bsb_account",
    "patient_id",
    "medical_record_number",
    "healthcare_identifier",
]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def add_label(labels: list[dict], category: str, value: str, valid: bool = True) -> None:
    labels.append({"category": category, "value": value, "valid": valid})


def make_doc(index: int, rng: random.Random, profile: str) -> tuple[dict, dict]:
    first = rng.choice(FIRST_NAMES)
    last = rng.choice(LAST_NAMES)
    last_clean = last.lower().replace("'", "")
    full_name = f"{first} {last}"
    dob = f"{rng.randint(1, 28):02d}/{rng.randint(1, 12):02d}/{rng.randint(1940, 2008)}"
    street_no = rng.randint(1, 250)
    address = f"{street_no} {rng.choice(STREETS)}, {rng.choice(SUBURBS)} NSW {rng.randint(2000, 2999)}"
    email = f"{first.lower()}.{last_clean}{index}@example.gov.au"
    phone = f"04{rng.randint(10000000, 99999999)}"
    tfn = "123 456 782"
    abn = "53 004 085 616"
    acn = "004 085 616"
    medicare = "2123 45670 1"
    driver_licence = f"NSW{rng.randint(100000, 999999)}"
    passport = f"N{rng.randint(1000000, 9999999)}"
    crn = f"{rng.randint(100000000, 999999999)}A"
    bsb = f"{rng.randint(100, 999)}-{rng.randint(100, 999)}"
    account = f"{rng.randint(10000000, 99999999)}"
    patient_id = f"PID-{rng.randint(100000, 999999)}"
    mrn = f"MRN {rng.randint(1000000, 9999999)}"
    ihi = "8003 6000 0000 0000"

    labels: list[dict] = []
    fragments: list[str] = []

    include_all = profile in {"mixed", "clinical"}
    if include_all or rng.random() < 0.7:
        fragments.append(f"Patient {full_name} attended review.")
        add_label(labels, "name", full_name)
    if include_all or rng.random() < 0.6:
        fragments.append(f"Date of birth: {dob}.")
        add_label(labels, "date_of_birth", dob)
    if profile != "clinical" and (include_all or rng.random() < 0.5):
        fragments.append(f"Residential address is {address}.")
        add_label(labels, "address", address)
    if profile != "clinical" and (include_all or rng.random() < 0.6):
        fragments.append(f"Contact email {email} and mobile {phone}.")
        add_label(labels, "email", email)
        add_label(labels, "phone", phone)
    if profile in {"mixed", "government"}:
        fragments.append(f"TFN {tfn}; ABN {abn}; ACN {acn}.")
        add_label(labels, "tfn", tfn)
        add_label(labels, "abn", abn)
        add_label(labels, "acn", acn)
        fragments.append(f"Medicare number {medicare}; driver licence {driver_licence}; passport {passport}; CRN {crn}.")
        add_label(labels, "medicare", medicare)
        add_label(labels, "driver_licence", driver_licence)
        add_label(labels, "passport", passport)
        add_label(labels, "crn", crn)
        fragments.append(f"Bank details BSB {bsb}, account {account}.")
        add_label(labels, "bsb_account", bsb)
    if profile in {"mixed", "clinical"}:
        fragments.append(f"Patient ID: {patient_id}; Medical Record Number: {mrn}; IHI {ihi}.")
        add_label(labels, "patient_id", patient_id)
        add_label(labels, "medical_record_number", mrn)
        add_label(labels, "healthcare_identifier", ihi)

    if profile == "negative":
        fragments = [
            "This operational note contains no direct personal identifiers.",
            "Reference codes ABC-123 and XYZ-999 are internal non-person records.",
            "The team reviewed aggregate counts only.",
        ]
        labels = []

    if rng.random() < 0.2 and profile != "negative":
        invalid_tfn = "123 456 789"
        fragments.append(f"Invalid checksum control TFN {invalid_tfn} should not count as valid.")
        add_label(labels, "tfn", invalid_tfn, valid=False)

    text = " ".join(fragments)
    doc_id = f"synthetic-{profile}-{index:06d}"
    return {"id": doc_id, "text": text, "profile": profile}, {"id": doc_id, "labels": labels}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic synthetic PII scale-test corpora.")
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--profile", choices=["mixed", "clinical", "government", "negative"], default="mixed")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    docs: list[dict] = []
    labels: list[dict] = []
    counts: Counter[str] = Counter()

    for i in range(args.count):
        doc, expected = make_doc(i, rng, args.profile)
        docs.append(doc)
        labels.append(expected)
        for item in expected["labels"]:
            if item.get("valid", True):
                counts[item["category"]] += 1

    write_jsonl(args.out / "documents.jsonl", docs)
    write_jsonl(args.out / "expected_labels.jsonl", labels)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": args.count,
        "seed": args.seed,
        "profile": args.profile,
        "valid_label_counts": dict(sorted(counts.items())),
        "category_keys": CATEGORY_KEYS,
        "synthetic_only": True,
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
