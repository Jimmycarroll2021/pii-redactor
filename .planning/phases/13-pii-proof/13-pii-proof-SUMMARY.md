# Phase 13: PII Proof - Summary

**Status:** Complete
**Completed:** 2026-05-03

## Work Completed

- Created focused proof fixture with Australian government and medical identifiers.
- Ran qwen2.5:7b de-PII benchmark over the proof fixture.
- Published scale-tests/reports/pii-proof-qwen25-7b.md.

## Result

- Documents: 2
- Safe-payload leaks: 0
- qwen detected LLM-only fields: name, date_of_birth, address
- Gate: pass
