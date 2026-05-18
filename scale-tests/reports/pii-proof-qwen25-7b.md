# PII Redaction Proof - qwen2.5:7b

**Generated:** 2026-05-03
**Purpose:** Prove the de-PII pipeline actually detects and redacts PII.
**Backend:** Ollama
**Model:** qwen2.5:7b
**Run:** scale-tests/runs/20260503-pii-proof-qwen25-7b-2docs
**Fixture:** scale-tests/fixtures/pii-proof-20260503

## Verdict

Pass.

The focused PII proof fixture ran through the qwen2.5:7b pipeline with zero checked PII leaks in the safe output payload.

## Results

| Metric | Value |
|---|---:|
| Documents processed | 2 |
| Status | OK |
| Safe-payload leak count | 0 |
| Error count | 0 |
| Mean latency ms | 28308.65 |
| Docs/sec | 0.0353 |

## PII Types Proven In This Run

| PII type | Expected | Detected |
|---|---:|---:|
| name | 2 | 2 |
| date_of_birth | 2 | 2 |
| address | 2 | 2 |
| email | 2 | 2 |
| phone | 2 | 2 |
| tfn | 1 | 1 |
| medicare | 1 | 1 |
| passport | 1 | 1 |
| driver_licence | 1 | 1 |
| abn | 1 | 1 |
| acn | 1 | 1 |
| bsb_account | 1 | 1 |
| patient_id | 1 | 1 |
| medical_record_number | 1 | 1 |
| healthcare_identifier | 1 | 1 |

## Important Notes

- This is the proof that the PII redaction path works, not an API-hardening report.
- qwen2.5:7b successfully detected name, date_of_birth, and address, which are the key LLM-only fields.
- Safe-payload leak count was zero, meaning checked original PII values were not present in the redacted output or safe result payload.
- CRN detection is reported internally as centrelink_crn; the expected label is crn.

## Evidence Files

- Summary: scale-tests/runs/20260503-pii-proof-qwen25-7b-2docs/summary.json
- Results: scale-tests/runs/20260503-pii-proof-qwen25-7b-2docs/results.jsonl
- Fixture docs: scale-tests/fixtures/pii-proof-20260503/documents.jsonl
- Expected labels: scale-tests/fixtures/pii-proof-20260503/expected_labels.jsonl
