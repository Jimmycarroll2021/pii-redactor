# Phase 6: Audit Mode Comparison - Plan

**Status:** Planned
**Mode:** Autonomous GSD

## Goal

Prove the de-PII project has a safe audit posture for local validation and pilot preparation.

## Tasks

1. Extend the library benchmark summary with audit evidence.
2. Run deterministic disabled-audit benchmark.
3. Run deterministic encrypted-audit benchmark.
4. Produce an audit-mode comparison report.
5. Update GSD state with Phase 6 completion and next autonomous gate.

## Acceptance Criteria

- Disabled audit mode produces no audit log.
- Encrypted audit mode produces audit rows.
- Encrypted audit mode has encrypted value entries.
- Encrypted audit mode has zero plaintext leak count for checked values.
- Existing safe-payload leak count remains zero in both runs.

## Verification

Use scale-tests/run_library_benchmark.py against scale-tests/fixtures/synthetic-1000-seed42 with backend=mock and limit=20.
