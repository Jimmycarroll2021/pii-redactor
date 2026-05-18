# de-PII Model Readiness Gate

**Generated:** 2026-05-03
**Project:** PII Redactor
**Current validation model:** qwen2.5:7b via Ollama
**Current readiness level:** Controlled local testing / demo

## Decision

The de-PII model is ready for controlled local validation and demo workflows. It is not yet ready for pilot or production use.

## Current trustworthy evidence

| Evidence | Value |
|----------|-------|
| Model | qwen2.5:7b |
| Backend | Ollama through FastAPI /redact/batch |
| Corrected identity path | Yes - HTTP benchmark sends document_id |
| Requested docs | 20 |
| Processed docs | 20 |
| Batches | 10/10 |
| Status | OK |
| Error count | 0 |
| Leak count | 0 |
| Docs/sec | 0.0441 |
| Estimated docs/day | 3811 |

## What is ready

- End-to-end de-identification flow works through the Python pipeline and FastAPI batch endpoint.
- qwen2.5:7b loads and runs locally through Ollama.
- Corrected HTTP benchmark identity mapping now supports valid expected-label leak checks.
- The corrected qwen2.5:7b 20-document baseline completed with zero leaks and zero errors.
- Medical identifiers are part of the supported detection/redaction surface: patient ID, medical record number, and healthcare identifier.
- Safe downstream output includes redacted text, spans without original values, and safe PII table rows.

## What is not ready

- Production readiness is not established.
- Pilot readiness is not established.
- Corrected qwen2.5:7b sample size is still small at 20 documents.
- Throughput is slow at 0.0441 docs/sec, roughly 22.7 seconds per document.
- Audit-mode comparison has not been completed for corrected qwen2.5:7b runs.
- Older HTTP leak results before the document_id fix are not authoritative.
- No real PII datasets should be used; all validation remains synthetic-only unless a formal privacy process exists.

## Known caveats

- Older HTTP benchmark runs sent id; FastAPI ignored it and generated UUIDs, so expected-label leak matching from those runs is invalid.
- qwen2.5:72b was removed because it was too large for this host profile.
- qwen2.5:7b is usable but slow; large corrected runs must use --resume chunks.
- Mock 1,000-document evidence proves harness capacity, not LLM quality.

## Gates before pilot readiness

1. Complete a corrected qwen2.5:7b run to at least 40 documents with zero leaks.
2. Run audit disabled vs encrypted audit comparison on corrected identity-mapped input.
3. Confirm no original PII appears in redacted text, spans, safe PII table, or non-encrypted logs.
4. Add false-positive and false-negative examples from synthetic data only.
5. Document acceptable throughput expectations for local use.

## Gates before production readiness

1. Complete larger corrected qwen2.5:7b benchmark in resumable chunks.
2. Add operational guidance for API key, audit key, encrypted audit log handling, and retention.
3. Add monitoring for error rate, leak count, timeout count, and docs/sec.
4. Perform security/privacy review of re-identification and audit access.
5. Define deployment hardware requirements or explicitly restrict use to local controlled workflows.

## Recommended next GSD action

Run Phase 6: Audit Mode Comparison.

Target output should compare corrected qwen2.5:7b or mock-equivalent audit behavior across disabled and encrypted audit modes without using real PII.
