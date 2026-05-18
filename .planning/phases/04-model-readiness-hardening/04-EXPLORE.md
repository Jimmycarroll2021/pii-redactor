# GSD Explore: de-PII Model Readiness

## Question

Is the de-PII model ready, and if not, what is the fastest path to a defensible ready state?

## Findings

- The production-like target should be `qwen2.5:7b`, not ad-hoc `pg-*` models.
- `qwen2.5:7b` fits and completes corrected runs, but it is slow.
- Corrected HTTP runs must send `document_id`; older runs that sent `id` cannot be trusted for leak validation.
- Resume semantics incorrectly marked completed resumed runs as `PARTIAL` because final status compared processed total against remaining documents.
- `.planning/STATE.md` was corrupted by leaked PowerShell here-string text and must be treated as an artifact needing repair.

## Decision

Readiness hardening should prioritize evidence correctness over larger benchmark volume.

## Route

Create a focused readiness-hardening phase that fixes benchmark semantics, repairs state, and records qwen2.5:7b as the current validation model.
