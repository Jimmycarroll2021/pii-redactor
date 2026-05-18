# De-PII Final Readiness Package

**Generated:** 2026-05-03
**Project:** KnowledgeGraph/tools/pii-redactor
**Model target:** qwen2.5:7b via local Ollama
**Readiness decision:** Ready for controlled local validation/demo. Not ready for production or unsupervised pilot.

## Executive Status

The project now has a working local de-PII pipeline with deterministic regex/checksum detection, local Ollama-backed LLM extraction, safe redaction output, encrypted audit-mode validation, and scale-test harnesses.

The main production blocker is not basic functionality. It is operational confidence: larger corrected qwen runs, service lifecycle stability, false-positive/false-negative review, and production privacy/security controls still need to be completed before handling real sensitive documents at pilot scale.

## Evidence Matrix

| Area | Result | Evidence |
|---|---|---|
| Audit disabled mode | Pass: no audit log written | scale-tests/reports/audit-mode-comparison.md |
| Audit encrypted mode | Pass: 285 audit rows, 285 encrypted values, zero plaintext leaks | scale-tests/reports/audit-mode-comparison.md |
| qwen2.5:7b config path | Pass: benchmark now inherits env config and uses selected model | scale-tests/reports/qwen25-7b-model-path-hardening.md |
| qwen2.5:7b bounded model validation | Pass: 3 docs, 0 leaks | scale-tests/runs/20260503-library-ollama-qwen25-7b-corrected-3docs |
| Corrected HTTP evidence | Partial/pass: 22 docs, 0 leaks, 0 errors before service-runner instability | scale-tests/runs/20260502-121821-http-ollama-qwen25-7b-10docs-c1-corrected |
| Overall readiness gate | Controlled validation/demo only | scale-tests/reports/de-pii-readiness-gate.md |

## Current Working Configuration

Use this for local qwen validation:

`powershell
$env:PIIR_BACKEND='ollama'
$env:PIIR_OLLAMA_MODEL='qwen2.5:7b'
$env:PIIR_OLLAMA_URL='http://127.0.0.1:11434'
$env:PIIR_LLM_TIMEOUT_SECONDS='600'
$env:PIIR_LLM_RETRIES='1'
$env:PIIR_MAX_CONCURRENCY='1'
$env:PIIR_AUDIT_ENABLED='false'
`

Fast deterministic regression gate:

`powershell
py -3.12 scale-tests\run_library_benchmark.py --documents scale-tests\fixtures\synthetic-1000-seed42\documents.jsonl --expected scale-tests\fixtures\synthetic-1000-seed42\expected_labels.jsonl --backend mock --audit-mode encrypted --limit 20 --out scale-tests\runs\<run-name>
`

Bounded qwen model gate:

`powershell
py -3.12 scale-tests\run_library_benchmark.py --documents scale-tests\fixtures\synthetic-1000-seed42\documents.jsonl --expected scale-tests\fixtures\synthetic-1000-seed42\expected_labels.jsonl --backend ollama --audit-mode disabled --limit 3 --out scale-tests\runs\<run-name>
`

## What Is Done

- PII redaction library exists and runs locally.
- Australian structured identifiers are covered by deterministic validation/redaction paths.
- LLM-backed extraction works with qwen2.5:7b after benchmark config hardening.
- Audit-disabled and audit-encrypted modes are validated.
- Scale-test fixture and benchmark harnesses exist.
- Reports exist for readiness, audit posture, and qwen path hardening.
- GSD planning artifacts exist through final handoff.

## What Is Not Done

- No production approval for real sensitive documents.
- No large corrected qwen2.5:7b run beyond bounded local validation.
- HTTP service lifecycle needs hardening; service startup must consistently use Python 3.12 with FastAPI/Uvicorn installed.
- No human false-positive/false-negative review set yet.
- No deployment profile for secrets, audit-key rotation, retention, access control, monitoring, or incident response.

## Production Blockers

1. Run a larger corrected qwen validation set with stable service lifecycle.
2. Create a curated false-positive/false-negative review set across Australian government and medical document styles.
3. Decide audit retention mode for real data: disabled, encrypted local audit, or metadata-only.
4. Add production API authentication and secret handling for every served deployment.
5. Add operational monitoring for LLM failures, fallback-only redactions, timeouts, and leak-check regressions.

## Final Decision

The project is not fucked. It is functional and has concrete validation evidence.

It is also not production-ready. The honest status is: ready for controlled local demo and further validation, with clear production blockers documented.

## Service Lifecycle Hardening Update

Added repeatable qwen FastAPI lifecycle scripts:

- `scale-tests/start_qwen_api.ps1`
- `scale-tests/run_qwen_http_validation.ps1`

These remove Python interpreter ambiguity and encode the correct benchmark behavior: pass the base URL only because the runner appends `/redact/batch` internally.

This hardens the validation path but does not replace the need to run a larger corrected qwen HTTP validation when runtime is available.

## Expanded qwen Validation Update

A stable 4-document qwen2.5:7b library validation pass completed after the environment-config fix.

- Run: scale-tests/runs/20260503-library-ollama-qwen25-7b-corrected-4docs
- Report: scale-tests/reports/qwen25-7b-expanded-library-validation.md
- Documents: 4
- Safe-payload leaks: 0
- LLM-only fields detected: name, date_of_birth, address

## Calibration Review Pack Update

Added human-review tooling for false-positive and false-negative calibration.

- Exporter: `scale-tests/export_review_pack.py`
- Initial review pack: `scale-tests/review-packs/20260503-mock-5docs`
- Calibration report: `scale-tests/reports/calibration-review-pack.md`

This creates the review workflow but does not replace actual human calibration. Human review remains required before production or unsupervised pilot use.

## API Security Hardening Update

Added production-style API authentication controls.

- `PIIR_REQUIRE_API_KEY=true` fails startup if `PIIR_API_KEY` is missing.
- `/redact` and `/redact/batch` use `PIIR_API_KEY`.
- `/reidentify` supports `PIIR_REIDENTIFY_API_KEY` and falls back to `PIIR_API_KEY` only if no separate key is configured.
- API key comparisons use constant-time comparison.

Remaining production work: secret storage/rotation, role-based re-identification authorization, TLS/network controls, and operational monitoring.

## Focused PII Proof Update

Created and ran a focused qwen2.5:7b proof fixture covering Australian government and medical identifiers.

- Report: scale-tests/reports/pii-proof-qwen25-7b.md
- Run: scale-tests/runs/20260503-pii-proof-qwen25-7b-2docs
- Documents: 2
- Safe-payload leaks: 0
- Key LLM-only fields detected: name, date_of_birth, address

## Contextual PII Proof Update

Created and ran a richer qwen2.5:7b proof pack across six document contexts.

- Report: scale-tests/reports/pii-context-proof-qwen25-7b.md
- Run: scale-tests/runs/20260503-pii-context-proof-qwen25-7b-6docs
- Documents: 6
- Checked PII leaks: 0
- Contexts: clinical note, case email, intake form, business record, referral letter, free-text case note

## 2,000-Document PII Smoke Update

Generated and ran a 2,000-document synthetic PII smoke test.

- Report: scale-tests/reports/pii-smoke-2000docs.md
- Run: scale-tests/runs/20260503-pii-smoke-mock-2000docs
- Fixture: scale-tests/fixtures/synthetic-2000-seed43
- Documents: 2000
- Checked PII leaks: 0
- Status: OK
