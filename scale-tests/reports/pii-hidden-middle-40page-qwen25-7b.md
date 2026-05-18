# Hidden-Middle Long Document PII Proof - qwen2.5:7b

**Generated:** 2026-05-03
**Purpose:** Prove PII is detected when buried in the middle of a long 40-page document.
**Backend:** Ollama
**Model:** qwen2.5:7b
**Run:** scale-tests/runs/20260503-pii-hidden-middle-40page-qwen25-7b
**Fixture:** scale-tests/fixtures/pii-hidden-middle-40page-20260503

## Verdict

Pass.

A 40-page synthetic long document was generated with PII only on page 21. The qwen2.5:7b pipeline detected and redacted the hidden PII with zero checked leaks in the safe output payload.

## Document Setup

| Field | Value |
|---|---:|
| Pages | 40 |
| PII page | 21 |
| Character length | 45,558 |
| Documents processed | 1 |

## Results

| Metric | Value |
|---|---:|
| Status | OK |
| Checked PII leaks | 0 |
| Runtime ms | 265754.22 |
| Docs/sec | 0.00376 |

## Hidden PII Coverage

| PII type | Expected | Detected |
|---|---:|---:|
| name | 1 | 1 |
| date_of_birth | 1 | 1 |
| address | 1 | 1 |
| email | 1 | 1 |
| phone | 1 | 1 |
| tfn | 1 | 1 |
| medicare | 1 | 1 |
| patient_id | 1 | 1 |
| medical_record_number | 1 | 1 |
| healthcare_identifier | 1 | 1 |

## Evidence Files

- Summary: scale-tests/runs/20260503-pii-hidden-middle-40page-qwen25-7b/summary.json
- Results: scale-tests/runs/20260503-pii-hidden-middle-40page-qwen25-7b/results.jsonl
- Fixture docs: scale-tests/fixtures/pii-hidden-middle-40page-20260503/documents.jsonl
- Human-readable generated document: scale-tests/fixtures/pii-hidden-middle-40page-20260503/document-preview.txt
- Expected labels: scale-tests/fixtures/pii-hidden-middle-40page-20260503/expected_labels.jsonl
