# Contextual PII Proof - qwen2.5:7b

**Generated:** 2026-05-03
**Purpose:** Prove qwen-backed de-PII works across varied document contexts.
**Backend:** Ollama
**Model:** qwen2.5:7b
**Run:** scale-tests/runs/20260503-pii-context-proof-qwen25-7b-6docs
**Fixture:** scale-tests/fixtures/pii-context-proof-20260503

## Verdict

Pass.

All six contextual documents were processed with zero checked PII leaks in the safe output payload.

## Contexts Tested

| Doc | Context |
|---|---|
| context-proof-001-clinical-note | Clinical progress note |
| context-proof-002-case-email | Caseworker email/update |
| context-proof-003-intake-form | Intake form |
| context-proof-004-business-record | Business/contact record |
| context-proof-005-referral-letter | Medical referral letter |
| context-proof-006-free-text-case-note | Free-text home visit case note |

## Results

| Metric | Value |
|---|---:|
| Documents processed | 6 |
| Status | OK |
| Checked PII leaks | 0 |
| Docs/sec | 0.0643 |
| Mean latency ms | 15559.54 |

## PII Coverage Observed

| PII type | Expected | Detected |
|---|---:|---:|
| name | 6 | 9 |
| date_of_birth | 4 | 4 |
| address | 6 | 6 |
| email | 4 | 4 |
| phone | 4 | 4 |
| tfn | 2 | 2 |
| medicare | 2 | 2 |
| passport | 2 | 2 |
| driver_licence | 1 | 1 |
| abn | 1 | 1 |
| acn | 1 | 1 |
| bsb_account | 1 | 1 |
| patient_id | 1 | 1 |
| medical_record_number | 2 | 2 |
| healthcare_identifier | 1 | 1 |

## Interpretation

This is the strongest current proof that the qwen-backed de-PII path works across realistic document styles. It covers prose, forms, emails, clinical records, business records, and case notes.

The safe output payload had zero checked PII leaks.

## Evidence Files

- Summary: scale-tests/runs/20260503-pii-context-proof-qwen25-7b-6docs/summary.json
- Results: scale-tests/runs/20260503-pii-context-proof-qwen25-7b-6docs/results.jsonl
- Fixture docs: scale-tests/fixtures/pii-context-proof-20260503/documents.jsonl
- Expected labels: scale-tests/fixtures/pii-context-proof-20260503/expected_labels.jsonl
