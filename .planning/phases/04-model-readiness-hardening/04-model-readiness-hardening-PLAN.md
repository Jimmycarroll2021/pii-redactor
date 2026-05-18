# Phase 4 Plan: Model Readiness Hardening

## Goal

Make the de-PII model readiness evidence trustworthy enough for controlled local testing.

## Tasks

1. Fix resumed benchmark completion status so a run reports `OK` when total processed documents equals total requested documents.
2. Preserve `document_id` as the HTTP benchmark identity field so expected-label leak checks remain valid.
3. Repair `.planning/STATE.md` to remove corrupted PowerShell text and unresolved `$run` placeholders.
4. Regenerate the current qwen2.5:7b corrected report from existing completed 20-document evidence.
5. Record current model target, known caveats, and next readiness gate.

## Acceptance Criteria

- `scale-tests/run_http_batch_benchmark.py` reports completed resumed runs as `OK`.
- The qwen2.5:7b 20-document corrected baseline is recorded as the current trustworthy model evidence.
- `.planning/STATE.md` is readable Markdown with no here-string fragments.
- The next step is explicit: continue to 40 docs only if 20-doc evidence remains leak-free.

## Out of Scope

- Running 100 documents in one pass.
- Treating pg-qwen models as the main readiness model.
- Production-readiness claims.
