# De-PII Audit Mode Comparison

**Generated:** 2026-05-03
**Phase:** 6 - Audit Mode Comparison
**Backend:** mock
**Fixture:** scale-tests/fixtures/synthetic-1000-seed42
**Limit:** 20 documents per run

## Verdict

Pass for controlled local validation.

The audit-disabled run produced no audit log. The audit-encrypted run produced audit evidence with encrypted values and zero plaintext leaks for checked synthetic values. Both runs kept redacted safe-payload leak count at zero.

## Results

| Mode | Status | Documents | Safe payload leaks | Audit log exists | Audit lines | Encrypted values | Audit plaintext leaks |
|---|---:|---:|---:|---:|---:|---:|---:|
| disabled | OK | 20 | 0 | False | 0 | 0 | 0 |
| encrypted | OK | 20 | 0 | True | 285 | 285 | 0 |

## Evidence Paths

- Disabled run: scale-tests\runs\20260503-library-mock-audit-disabled-20docs
- Encrypted run: scale-tests\runs\20260503-library-mock-audit-encrypted-20docs
- Encrypted audit log: scale-tests\runs\20260503-library-mock-audit-encrypted-20docs\audit.jsonl

## Interpretation

Audit-disabled mode is appropriate when the safest operational posture is to retain no redaction audit trail.

Audit-encrypted mode is appropriate when traceability is required. In this validation run it wrote encrypted redaction values and did not expose checked plaintext PII in the audit file.

## Scope Limit

This phase validates audit storage mechanics with the deterministic mock backend. It does not replace qwen2.5:7b model-quality validation. The corrected qwen2.5:7b benchmark remains the model-readiness evidence for LLM extraction behavior.

## Gate Outcome

- Disabled audit mode: pass
- Encrypted audit mode: pass
- Safe-payload leak gate: pass
- Audit plaintext leak gate: pass

Overall: pass for controlled local validation and demo readiness.
