# PII Smoke Test - 2,000 Documents

**Generated:** 2026-05-03
**Run:** scale-tests/runs/20260503-pii-smoke-mock-2000docs
**Fixture:** scale-tests/fixtures/synthetic-2000-seed43
**Backend:** mock deterministic detector
**Documents:** 2000

## Verdict

Pass.

The 2,000-document synthetic PII smoke test completed with zero checked PII leaks in the safe output payload.

## Results

| Metric | Value |
|---|---:|
| Documents processed | 2000 |
| Status | OK |
| Checked PII leaks | 0 |
| Docs/sec | 1696.21 |
| Mean latency ms | 0.518 |
| Total seconds | 1.179 |

## Corpus Contents

The generated corpus contains 2,000 synthetic documents. Each document has expected labels across the configured PII set:

- name
- date_of_birth
- address
- email
- phone
- tfn
- abn
- acn
- medicare
- driver_licence
- passport
- crn
- bsb_account
- patient_id
- medical_record_number
- healthcare_identifier

## Checked Leak Scope

This high-volume smoke test proves structured PII redaction/leak safety at scale. The fast deterministic backend excludes name, address, and date_of_birth from leak assertions because those require LLM extraction.

qwen2.5:7b contextual proof for name, DOB, and address is documented separately in scale-tests/reports/pii-context-proof-qwen25-7b.md.

## Evidence Files

- Summary: scale-tests/runs/20260503-pii-smoke-mock-2000docs/summary.json
- Results: scale-tests/runs/20260503-pii-smoke-mock-2000docs/results.jsonl
- Fixture docs: scale-tests/fixtures/synthetic-2000-seed43/documents.jsonl
- Expected labels: scale-tests/fixtures/synthetic-2000-seed43/expected_labels.jsonl
