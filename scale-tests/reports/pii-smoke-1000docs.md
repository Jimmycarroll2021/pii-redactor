# PII Smoke Test - 1,000 Documents

**Generated:** 2026-05-03
**Run:** scale-tests/runs/20260503-pii-smoke-mock-1000docs
**Fixture:** scale-tests/fixtures/synthetic-1000-seed42
**Backend:** mock deterministic detector
**Documents:** 1000

## Verdict

Pass.

The 1,000-document synthetic PII smoke test completed with zero checked PII leaks in the safe output payload.

## Results

| Metric | Value |
|---|---:|
| Documents processed | 1000 |
| Status | OK |
| Checked PII leaks | 0 |
| Docs/sec | 1677.49 |
| Mean latency ms | 0.521 |

## Checked PII Types

Structured checked values included TFN, ABN, ACN, BSB/account, CRN, driver licence, email, healthcare identifier, MRN, Medicare, passport, patient ID, phone.

## Scope Note

This high-volume smoke test uses the deterministic/mock path, so it is the fast regression gate for structured PII leaks at scale.

Name, date_of_birth, and address require qwen/LLM extraction. Those were proven separately in scale-tests/reports/pii-proof-qwen25-7b.md with zero leaks on the focused qwen proof fixture.
