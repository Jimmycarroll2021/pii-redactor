"""Generate synthetic medical PII fixture for Wiest-style benchmarking.

Produces 50 clinical-note-style narratives with embedded PII and ground-truth labels.
Fully deterministic via seeded random — no external APIs, $0 spend.

Output:
  scale-tests/fixtures/synthetic-medical-50/documents.jsonl
  scale-tests/fixtures/synthetic-medical-50/expected_labels.jsonl

Schema matches existing benchmark fixtures: each doc has {id, text}; each
labels row has {id, labels:[{category, valid, value}]}.

>=10 of 50 docs include AU identifiers (Medicare, IHI) per PRD US-005.
"""

from __future__ import annotations

import json
import random
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pii_redactor.validators import validate_medicare


# ----------------------------- name pools ------------------------------------

FIRST_NAMES = [
    "Aiden", "Olivia", "Noah", "Ava", "Liam", "Mia", "Ethan", "Sophia",
    "Lucas", "Charlotte", "Mason", "Amelia", "Logan", "Isabella", "Oliver",
    "Harper", "Elijah", "Evelyn", "Jacob", "Abigail", "Benjamin", "Emily",
    "Michael", "Madison", "James", "Scarlett", "Henry", "Victoria",
    "Alexander", "Aria", "Sebastian", "Grace", "Daniel", "Chloe",
    "Matthew", "Camila", "Jackson", "Penelope", "David", "Riley",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson",
    "Martin", "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez",
    "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young",
    "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill",
]
DOCTOR_TITLES = ["Dr.", "Prof.", "A/Prof.", "Mr.", "Ms."]
HOSPITALS = [
    "Royal Prince Alfred Hospital", "Westmead Children's Hospital",
    "St Vincent's Hospital Sydney", "The Alfred Hospital",
    "Royal Melbourne Hospital", "Princess Alexandra Hospital",
    "Royal Adelaide Hospital", "Sir Charles Gairdner Hospital",
    "Royal Brisbane and Women's Hospital", "John Hunter Hospital",
    "Northern Beaches Hospital", "Cabrini Health Malvern",
]
STREETS = [
    "Macquarie Street", "Collins Street", "Bourke Street", "Pitt Street",
    "George Street", "Queen Street", "Elizabeth Street", "King William Road",
    "Adelaide Terrace", "St Kilda Road", "Brunswick Street", "Hay Street",
]
SUBURBS = [
    ("Sydney", "NSW", "2000"), ("Melbourne", "VIC", "3000"),
    ("Brisbane", "QLD", "4000"), ("Perth", "WA", "6000"),
    ("Adelaide", "SA", "5000"), ("Hobart", "TAS", "7000"),
    ("Darwin", "NT", "0800"), ("Canberra", "ACT", "2600"),
    ("Parramatta", "NSW", "2150"), ("Geelong", "VIC", "3220"),
    ("Newcastle", "NSW", "2300"), ("Bondi", "NSW", "2026"),
]

# ----------------------------- helpers ---------------------------------------


def gen_mobile(rng: random.Random) -> str:
    """AU mobile in '04XX XXX XXX' format."""
    return f"04{rng.randint(10, 99)} {rng.randint(100, 999)} {rng.randint(100, 999)}"


def gen_landline(rng: random.Random) -> str:
    area = rng.choice(["02", "03", "07", "08"])
    return f"({area}) {rng.randint(7000, 9999)} {rng.randint(1000, 9999)}"


def gen_dob(rng: random.Random) -> str:
    year = rng.randint(1935, 2010)
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    return f"{day:02d}/{month:02d}/{year}"


def gen_visit_date(rng: random.Random) -> str:
    year = 2026
    month = rng.randint(1, 5)
    day = rng.randint(1, 28)
    return f"{day:02d}/{month:02d}/{year}"


def gen_mrn(rng: random.Random) -> str:
    return f"MRN-{rng.randint(100000, 999999)}"


def gen_medicare(rng: random.Random) -> str:
    while True:
        n = "".join(str(rng.randint(0, 9)) for _ in range(10))
        if validate_medicare(n):
            return n


def gen_ihi(rng: random.Random) -> str:
    # IHI: 16-digit identifier prefixed with 8003 — keep as bare 16 digits to
    # match the existing healthcare_identifier regex which requires the
    # 4-4-4-4 grouped pattern (spaces or dashes).
    return f"8003 {rng.randint(1000, 9999)} {rng.randint(1000, 9999)} {rng.randint(1000, 9999)}"


def gen_address(rng: random.Random) -> str:
    num = rng.randint(1, 999)
    street = rng.choice(STREETS)
    suburb, state, pc = rng.choice(SUBURBS)
    return f"{num} {street}, {suburb} {state} {pc}"


def gen_email(first: str, last: str, rng: random.Random) -> str:
    domain = rng.choice(["example.com", "patient.health.au", "outlook.com"])
    return f"{first.lower()}.{last.lower()}{rng.randint(1, 99)}@{domain}"


def gen_name(rng: random.Random) -> tuple[str, str]:
    return rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)


def gen_doctor(rng: random.Random) -> str:
    title = rng.choice(DOCTOR_TITLES)
    _, last = gen_name(rng)
    return f"{title} {last}"


# ----------------------------- templates --------------------------------------

# Each template is a function (rng, include_au_id) -> (text, labels[]).
# Labels match existing PII categories the redactor supports:
#   name, address, date_of_birth, phone, email, medicare,
#   medical_record_number, healthcare_identifier, date

PII_CATEGORY_NAME = "name"
PII_CATEGORY_ADDRESS = "address"
PII_CATEGORY_DOB = "date_of_birth"
PII_CATEGORY_PHONE = "phone"
PII_CATEGORY_EMAIL = "email"
PII_CATEGORY_MEDICARE = "medicare"
PII_CATEGORY_MRN = "medical_record_number"
PII_CATEGORY_IHI = "healthcare_identifier"
PII_CATEGORY_DATE = "date"


def lbl(category: str, value: str) -> dict:
    return {"category": category, "valid": True, "value": value}


def tmpl_admission_note(rng: random.Random, include_au_id: bool) -> tuple[str, list[dict]]:
    first, last = gen_name(rng)
    full = f"{first} {last}"
    dob = gen_dob(rng)
    addr = gen_address(rng)
    mobile = gen_mobile(rng)
    mrn = gen_mrn(rng)
    doc = gen_doctor(rng)
    hospital = rng.choice(HOSPITALS)
    visit = gen_visit_date(rng)

    text = (
        f"ADMISSION NOTE — {hospital}\n"
        f"Patient: {full}, DOB {dob}. Residing at {addr}. "
        f"Mobile contact {mobile}. Medical record {mrn}. "
        f"Admitting clinician: {doc}. Date of admission: {visit}. "
        f"Reason for admission: acute chest pain, ruled out STEMI on troponin. "
        f"Plan: overnight observation, cardiology review in the morning."
    )
    labels = [
        lbl(PII_CATEGORY_NAME, full),
        lbl(PII_CATEGORY_DOB, dob),
        lbl(PII_CATEGORY_ADDRESS, addr),
        lbl(PII_CATEGORY_PHONE, mobile),
        lbl(PII_CATEGORY_MRN, mrn),
        lbl(PII_CATEGORY_NAME, doc),
        lbl(PII_CATEGORY_DATE, visit),
    ]
    if include_au_id:
        medicare = gen_medicare(rng)
        text += f" Medicare: {medicare}."
        labels.append(lbl(PII_CATEGORY_MEDICARE, medicare))
    return text, labels


def tmpl_discharge_summary(rng: random.Random, include_au_id: bool) -> tuple[str, list[dict]]:
    first, last = gen_name(rng)
    full = f"{first} {last}"
    dob = gen_dob(rng)
    addr = gen_address(rng)
    landline = gen_landline(rng)
    email = gen_email(first, last, rng)
    mrn = gen_mrn(rng)
    doc = gen_doctor(rng)
    discharged = gen_visit_date(rng)

    text = (
        f"DISCHARGE SUMMARY\n"
        f"Patient name: {full}; date of birth {dob}. Home address {addr}. "
        f"Contact landline {landline}, email {email}. Hospital file {mrn}. "
        f"Discharged on {discharged} under the care of {doc}. "
        f"Diagnosis: community-acquired pneumonia, treated with IV ceftriaxone "
        f"transitioned to oral amoxicillin/clavulanate. GP follow-up in 7 days."
    )
    labels = [
        lbl(PII_CATEGORY_NAME, full),
        lbl(PII_CATEGORY_DOB, dob),
        lbl(PII_CATEGORY_ADDRESS, addr),
        lbl(PII_CATEGORY_PHONE, landline),
        lbl(PII_CATEGORY_EMAIL, email),
        lbl(PII_CATEGORY_MRN, mrn),
        lbl(PII_CATEGORY_NAME, doc),
        lbl(PII_CATEGORY_DATE, discharged),
    ]
    if include_au_id:
        ihi = gen_ihi(rng)
        text += f" Healthcare identifier {ihi}."
        labels.append(lbl(PII_CATEGORY_IHI, ihi))
    return text, labels


def tmpl_referral(rng: random.Random, include_au_id: bool) -> tuple[str, list[dict]]:
    first, last = gen_name(rng)
    full = f"{first} {last}"
    dob = gen_dob(rng)
    mobile = gen_mobile(rng)
    addr = gen_address(rng)
    referring = gen_doctor(rng)
    specialist = gen_doctor(rng)
    referral_date = gen_visit_date(rng)

    text = (
        f"REFERRAL LETTER — Date: {referral_date}\n"
        f"Dear {specialist},\n"
        f"I am referring my patient {full} (DOB {dob}) who lives at {addr}. "
        f"Best contact mobile is {mobile}. "
        f"He/She presents with a 3-month history of progressive dyspnoea on exertion "
        f"and would benefit from a respiratory specialist review. "
        f"Pulmonary function tests attached.\n"
        f"Kind regards,\n{referring}"
    )
    labels = [
        lbl(PII_CATEGORY_NAME, full),
        lbl(PII_CATEGORY_DOB, dob),
        lbl(PII_CATEGORY_PHONE, mobile),
        lbl(PII_CATEGORY_ADDRESS, addr),
        lbl(PII_CATEGORY_NAME, referring),
        lbl(PII_CATEGORY_NAME, specialist),
        lbl(PII_CATEGORY_DATE, referral_date),
    ]
    if include_au_id:
        medicare = gen_medicare(rng)
        text += f"\nMedicare number: {medicare}."
        labels.append(lbl(PII_CATEGORY_MEDICARE, medicare))
    return text, labels


def tmpl_clinic_note(rng: random.Random, include_au_id: bool) -> tuple[str, list[dict]]:
    first, last = gen_name(rng)
    full = f"{first} {last}"
    dob = gen_dob(rng)
    mrn = gen_mrn(rng)
    doc = gen_doctor(rng)
    visit = gen_visit_date(rng)
    phone = gen_mobile(rng) if rng.random() < 0.5 else gen_landline(rng)

    text = (
        f"OUTPATIENT CLINIC NOTE — {visit}\n"
        f"Reviewed {full}, DOB {dob}, record {mrn} (clinician {doc}). "
        f"Patient reports good adherence to metformin 1g BD. HbA1c down from 9.2 to 7.4. "
        f"Blood pressure 128/82, BMI 31. Continue current regimen, repeat bloods in 3 months. "
        f"Patient reachable on {phone} for results."
    )
    labels = [
        lbl(PII_CATEGORY_NAME, full),
        lbl(PII_CATEGORY_DOB, dob),
        lbl(PII_CATEGORY_MRN, mrn),
        lbl(PII_CATEGORY_NAME, doc),
        lbl(PII_CATEGORY_DATE, visit),
        lbl(PII_CATEGORY_PHONE, phone),
    ]
    if include_au_id:
        medicare = gen_medicare(rng)
        text += f" Medicare {medicare} on file."
        labels.append(lbl(PII_CATEGORY_MEDICARE, medicare))
    return text, labels


def tmpl_pathology_request(rng: random.Random, include_au_id: bool) -> tuple[str, list[dict]]:
    first, last = gen_name(rng)
    full = f"{first} {last}"
    dob = gen_dob(rng)
    mrn = gen_mrn(rng)
    doc = gen_doctor(rng)
    req_date = gen_visit_date(rng)

    text = (
        f"PATHOLOGY REQUEST — {req_date}\n"
        f"Patient: {full} (DOB {dob}), file {mrn}. "
        f"Requesting clinician: {doc}. "
        f"Tests requested: FBC, U&E, LFTs, fasting glucose, TSH, lipid panel. "
        f"Clinical notes: routine 12-month diabetic screen, no acute concerns."
    )
    labels = [
        lbl(PII_CATEGORY_NAME, full),
        lbl(PII_CATEGORY_DOB, dob),
        lbl(PII_CATEGORY_MRN, mrn),
        lbl(PII_CATEGORY_NAME, doc),
        lbl(PII_CATEGORY_DATE, req_date),
    ]
    if include_au_id:
        ihi = gen_ihi(rng)
        text += f" IHI: {ihi}."
        labels.append(lbl(PII_CATEGORY_IHI, ihi))
    return text, labels


TEMPLATES = [
    tmpl_admission_note,
    tmpl_discharge_summary,
    tmpl_referral,
    tmpl_clinic_note,
    tmpl_pathology_request,
]


# ----------------------------- main -----------------------------------------


def generate(n_docs: int = 50, n_au: int = 15, seed: int = 17) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    docs: list[dict] = []
    labels_rows: list[dict] = []

    # Pre-decide which doc indices get AU identifiers (>=10 per PRD US-005 AC).
    au_indices = set(rng.sample(range(n_docs), n_au))

    for i in range(n_docs):
        tmpl = TEMPLATES[i % len(TEMPLATES)]
        text, labels = tmpl(rng, include_au_id=i in au_indices)
        doc_id = f"medical-{uuid.UUID(int=rng.getrandbits(128)).hex[:16]}"
        docs.append({"id": doc_id, "text": text})
        labels_rows.append({"id": doc_id, "labels": labels})
    return docs, labels_rows


def main() -> int:
    out_dir = ROOT / "scale-tests" / "fixtures" / "synthetic-medical-50"
    out_dir.mkdir(parents=True, exist_ok=True)
    docs, labels_rows = generate()

    docs_path = out_dir / "documents.jsonl"
    labels_path = out_dir / "expected_labels.jsonl"

    with docs_path.open("w", encoding="utf-8") as fh:
        for row in docs:
            fh.write(json.dumps(row) + "\n")
    with labels_path.open("w", encoding="utf-8") as fh:
        for row in labels_rows:
            fh.write(json.dumps(row) + "\n")

    au_count = sum(
        1
        for row in labels_rows
        if any(
            lab["category"] in {PII_CATEGORY_MEDICARE, PII_CATEGORY_IHI}
            for lab in row["labels"]
        )
    )
    total_labels = sum(len(row["labels"]) for row in labels_rows)
    label_chars = sum(len(d["text"]) for d in docs)
    print(f"Generated {len(docs)} docs at {docs_path}")
    print(f"Total labels: {total_labels}; AU-identifier docs: {au_count}/{len(docs)}")
    print(f"Mean doc length: {label_chars/len(docs):.0f} chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
