# State

Status: v1.1 in progress
Current focus: Audit Mode Comparison.
Last completed milestone: v1.0 Scale Evidence, archived 2026-04-30.

## Project Reference

See: .planning/PROJECT.md.

**Core value:** Prove, with repeatable local artifacts, that PII redaction works correctly and safely at batch scale without leaking original PII downstream.
**Current focus:** Compare audit disabled vs encrypted audit behavior after establishing corrected qwen2.5:7b baseline.

## Current readiness position

The de-PII model is ready for controlled local validation/demo. It is not yet pilot-ready or production-ready.

## Current model target

Use qwen2.5:7b for real-Ollama validation.

## Latest trustworthy qwen2.5:7b benchmark

| Model | Concurrency | Requested | Processed | Batches | Docs/sec | Estimated docs/day | Leak count | Status |
|-------|-------------|-----------|-----------|---------|----------|--------------------|------------|--------|
| qwen2.5:7b | 1 | 20 | 20 | 10/10 | 0.0441 | 3811 | 0 | OK |

## Latest artifacts

- Readiness gate: scale-tests/reports/de-pii-readiness-gate.md
- Corrected qwen2.5:7b report: scale-tests/reports/latest-http-ollama-qwen25-7b-CORRECTED-REPORT.md
- Phase 5 summary: .planning/phases/05-readiness-gate-report/05-readiness-gate-report-SUMMARY.md

## Next recommended action

Formalize and execute Phase 6: Audit Mode Comparison.

## Autonomous Update - 2026-05-03

- Phase 6: complete
- Report: scale-tests/reports/audit-mode-comparison.md
- Disabled audit: no audit log, zero safe-payload leaks
- Encrypted audit: 285 audit rows, 285 encrypted values, zero audit plaintext leaks
- Current readiness: controlled local validation/demo
- Next recommended phase: larger corrected qwen2.5:7b validation or false-positive/false-negative calibration

## Autonomous Update - 2026-05-03

- Phase 7: complete with bounded validation
- Fixed: library benchmark now inherits environment config before backend/audit overrides
- qwen2.5:7b corrected library run: 3 docs, 0 leaks
- Report: scale-tests/reports/qwen25-7b-model-path-hardening.md
- Remaining before project can be called done: final readiness package and operator handoff

## Autonomous Update - 2026-05-03

- Phase 8: complete
- Final report: scale-tests/reports/final-readiness-package.md
- Final readiness: controlled local validation/demo
- Not production-ready until larger qwen validation, HTTP lifecycle hardening, calibration review, and production security controls are complete
- Autonomous GSD workstream: complete through final handoff

## Autonomous Update - 2026-05-03

- Phase 9: complete
- Added: scale-tests/start_qwen_api.ps1
- Added: scale-tests/run_qwen_http_validation.ps1
- Updated: scale-tests/RUNBOOK.md
- Autonomous workstream status: complete for current machine-local de-PII validation package

## Autonomous Update - 2026-05-03

- Phase 10: complete
- Expanded qwen2.5:7b validation: 4 docs, 0 leaks
- Report: scale-tests/reports/qwen25-7b-expanded-library-validation.md
- Current readiness remains controlled local validation/demo; production still needs human calibration and long-run validation.

## Autonomous Update - 2026-05-03

- Phase 11: complete
- Added calibration exporter and sample review pack
- Report: scale-tests/reports/calibration-review-pack.md
- Remaining production gate: human reviewer must complete calibration findings before real data use

## Autonomous Update - 2026-05-03

- Phase 12: complete
- Added strict API auth mode and separate re-identification key support
- Report: scale-tests/reports/api-security-hardening.md
- Remaining production gates: long-run validation, completed human calibration, deployment secret storage/rotation, monitoring

## Autonomous Update - 2026-05-03

- Phase 13: complete
- Focus returned to proving PII redaction works
- qwen2.5:7b focused proof: 2 docs, 0 leaks
- Report: scale-tests/reports/pii-proof-qwen25-7b.md

## Smoke Test Update - 2026-05-03

- 1,000-doc PII smoke test: pass
- Run: scale-tests/runs/20260503-pii-smoke-mock-1000docs
- Report: scale-tests/reports/pii-smoke-1000docs.md
- Checked PII leaks: 0

## Contextual PII Proof Update - 2026-05-03

- qwen2.5:7b contextual proof: pass
- Documents: 6
- Checked PII leaks: 0
- Report: scale-tests/reports/pii-context-proof-qwen25-7b.md
- Contexts: clinical note, case email, intake form, business record, referral letter, free-text case note

## Smoke Test Update - 2026-05-03

- 2,000-doc PII smoke test: pass
- Run: scale-tests/runs/20260503-pii-smoke-mock-2000docs
- Report: scale-tests/reports/pii-smoke-2000docs.md
- Checked PII leaks: 0

## Hidden-Middle 40-Page PII Proof - 2026-05-03

- qwen2.5:7b long-doc proof: pass
- Pages: 40
- PII page: 21
- Checked PII leaks: 0
- Report: scale-tests/reports/pii-hidden-middle-40page-qwen25-7b.md

## Kaggle PII Data Test - 2026-05-03

- Downloaded Kaggle-derived PII data mirror
- Converted 945 PII-labelled records into project benchmark format
- Ran qwen2.5:7b on diverse 12-doc Kaggle subset
- Result: fail for Kaggle-style coverage
- Checked PII leaks: 11
- Report: scale-tests/reports/kaggle-pii-diverse-12-qwen25-7b.md

## Kaggle Pull/Test Update - 2026-05-03

- Official Kaggle download still blocked by competition access: 403 Forbidden
- Public Kaggle-derived mirror tested
- Broad mirror smoke: 945 docs, 76 checked leaks
- qwen diverse subset: 12 docs, 11 checked leaks
- Report: scale-tests/reports/kaggle-pii-pull-and-test.md

## Public PII Test Data Update - 2026-05-03

- Added AI4Privacy OpenPII English 500 fixture
- Added Gretel PII Masking English 500 fixture
- Existing Kaggle-derived fixture remains available
- Report: scale-tests/reports/public-pii-test-data-index.md
- These datasets intentionally expose current generalization gaps and are ready for fix/test loops

## Proper PII Test Setup - 2026-05-03

- Implemented consolidated eval suite and fixture registry
- Converted user-supplied ZIP datasets into fixtures
- Added username/generic_id categories and targeted regex coverage
- Latest proper deterministic eval: PASS
- Run: scale-tests/runs/20260503-pii-eval-proper-pass
- Report: scale-tests/reports/proper-pii-test-setup.md

## 2026-05-03 Full all-data PII eval pass

- Ran `scale-tests/fixtures/registry-full.json` through `scale-tests/run_pii_eval_suite.py --profile full --backend mock`.
- Final run: `scale-tests/runs/20260503-pii-eval-full-all-data-final6`.
- Result: PASS, 0 failed fixtures, 0 scored leaks.
- Scope: 11 fixture groups, 48,382 documents.
- Report: `scale-tests/reports/full-all-data-pii-test.md`.
- Notes: benchmark now excludes volatile `processed_at` from leak matching to avoid false positives on time labels; deterministic recognizers expanded for emails, usernames, bare domains, and date/time edge cases.

## 2026-05-03 Autonomous PII experiment loop

- Qwen quick run passed: `scale-tests/runs/20260503-pii-eval-qwen-quick-1`.
- Qwen proper run passed: `scale-tests/runs/20260503-pii-eval-qwen-proper-1`.
- Encrypted audit full run passed: `scale-tests/runs/20260503-pii-eval-encrypted-audit-full-2`.
- Encrypted audit scope: 48382 documents, 0 failed fixtures, 0 plaintext audit metadata leaks.
- Report: `scale-tests/reports/autonomous-pii-experiments-20260503.md`.

## 2026-05-03 Adversarial/Qwen autonomous experiments

- Added adversarial fixture: `scale-tests/fixtures/adversarial-edgecases-20260503` with 120 punctuation/code/filler edge-case documents.
- Mock adversarial run passed: `scale-tests/runs/20260503-adversarial-edgecases-mock-1`.
- Encrypted audit adversarial run passed: `scale-tests/runs/20260503-adversarial-edgecases-audit-1`.
- Fixed Ollama integration for local qwen2.5:7b by adding generate fallback, JSON mode, and common env aliases.
- Real Qwen adversarial full run passed: `scale-tests/runs/20260503-adversarial-edgecases-qwen-json-full-1`, 120 docs, 0 leaks.
- Report updated: `scale-tests/reports/autonomous-pii-experiments-20260503.md`.

## 2026-05-03 Corrected real-Qwen registry reruns

- Real Qwen quick registry run passed after Ollama fix: `scale-tests/runs/20260503-pii-eval-qwen-real-quick-1`.
- Real Qwen proper registry run passed after Ollama fix: `scale-tests/runs/20260503-pii-eval-qwen-real-proper-1`.
- Report updated: `scale-tests/reports/autonomous-pii-experiments-20260503.md`.

## 2026-05-03 LLM-only ablation hardening

- Qwen LLM-only no-regex ablation initially exposed misses on time-only dates, suffix dates, and SSN-style generic IDs.
- Tightened prompt rules/examples for unsupported categories, SSN-style generic IDs, and exact date substring extraction.
- Final full adversarial LLM-only run passed: `scale-tests/runs/20260503-adversarial-edgecases-qwen-llm-only-full-1`, 120 docs, 0 leaks.
- Added benchmark support for `--disable-regex-prepass`; smoke run passed at `scale-tests/runs/20260503-adversarial-edgecases-qwen-cli-llm-only-smoke-1`.
- Report updated: `scale-tests/reports/autonomous-pii-experiments-20260503.md`.

## 2026-05-03 Long-doc boundary and pattern-tuning experiments

- Added long-doc boundary fixture: `scale-tests/fixtures/longdoc-chunk-boundary-20260503`.
- Real Qwen boundary run passed: `scale-tests/runs/20260503-longdoc-boundary-qwen-1`, 6 docs, 0 leaks.
- Tightened generic mixed-ID regex to uppercase-only to reduce lowercase filler false positives.
- Restored high-recall bare username matching after full registry showed username leak regressions.
- Full deterministic registry passed after tuning: `scale-tests/runs/20260503-pii-eval-full-all-data-tight-patterns-2`.
- Report updated: `scale-tests/reports/autonomous-pii-experiments-20260503.md`.

## 2026-05-03 Encrypted audit revalidation after tuning

- Full encrypted audit registry revalidation passed: `scale-tests/runs/20260503-pii-eval-encrypted-audit-full-tight-patterns-1`.
- Scope: 48382 docs, 0 failed fixtures.
- Report updated: `scale-tests/reports/autonomous-pii-experiments-20260503.md`.

## 2026-05-03 Local model comparison smoke

- Ran 32B LLM-only adversarial smoke: `scale-tests/runs/20260503-adversarial-edgecases-qwen32b-cli-llm-only-smoke-1`, 12 docs, 0 leaks, 0.0211 docs/sec.
- Compared with 7B CLI smoke: `scale-tests/runs/20260503-adversarial-edgecases-qwen-cli-llm-only-smoke-1`, 0.1498 docs/sec.
- Default remains `qwen2.5:7b` for speed/quality balance.
- Report updated: `scale-tests/reports/autonomous-pii-experiments-20260503.md`.

## 2026-05-03 False-positive and strict username experiments

- Added benign technical fixture: `scale-tests/fixtures/benign-false-positive-20260503`.
- Added reserved/test-domain, product-code, and technical-token suppressions.
- Added optional `PIIR_USERNAME_MODE=strict` to suppress bare alphanumeric username matches.
- Strict benign run: `scale-tests/runs/20260503-benign-false-positive-mock-strict-2`, username detections 1600.
- Strict adversarial run stayed leak-free: `scale-tests/runs/20260503-adversarial-edgecases-mock-strict-username-2`.
- Default full registry stayed PASS: `scale-tests/runs/20260503-pii-eval-full-all-data-fp-tuning-2`.
- Report updated: `scale-tests/reports/autonomous-pii-experiments-20260503.md`.

## 2026-05-03 Expanded autonomous registry checkpoint

- Created `scale-tests/fixtures/registry-autonomous.json` with 14 fixtures and 48,758 docs.
- Deterministic expanded registry passed: `scale-tests/runs/20260503-pii-eval-autonomous-registry-mock-1`.
- Encrypted audit expanded registry passed: `scale-tests/runs/20260503-pii-eval-autonomous-registry-encrypted-audit-1`.
- Report updated: `scale-tests/reports/autonomous-pii-experiments-20260503.md`.

## 2026-05-03 Integrity and Qwen expanded-registry checkpoint

- Compile check passed across `pii_redactor` and `scale-tests`.
- Real Qwen quick expanded-registry run passed: `scale-tests/runs/20260503-pii-eval-autonomous-registry-qwen-quick-1`.
- Report updated: `scale-tests/reports/autonomous-pii-experiments-20260503.md`.

## 2026-05-03 Async pipeline concurrency checks

- Async mock run passed: `scale-tests/runs/20260503-adversarial-async-mock-1`, 120 docs, 0 leaks.
- Async Qwen run passed: `scale-tests/runs/20260503-adversarial-async-qwen-1`, 8 docs, 0 leaks.
- Report updated: `scale-tests/reports/autonomous-pii-experiments-20260503.md`.

## 2026-05-03 Audit and serialization safety checks

- Audit re-identification round trip passed: `scale-tests/runs/20260503-audit-reidentify-roundtrip-1`.
- Placeholder/result serialization safety passed: `scale-tests/runs/20260503-placeholder-safety-1`.
- Report updated: `scale-tests/reports/autonomous-pii-experiments-20260503.md`.

## 2026-05-03 Strict username full-registry tradeoff

- Strict username mode full-registry run failed as expected: `scale-tests/runs/20260503-pii-eval-full-strict-username-tradeoff-1`.
- Total scored leaks under strict mode: 1127; failed fixtures: 4.
- Default high-recall username mode remains required for production leak prevention.
- Report updated: `scale-tests/reports/autonomous-pii-experiments-20260503.md`.

## 2026-05-04 Production hardening checkpoint

- Added fail-closed LLM extraction mode via `PIIR_FAIL_ON_LLM_ERROR=true`.
- Added `scale-tests/run_production_gate.py`.
- Added `docs/PRODUCTION_HARDENING.md`.
- Added `.github/workflows/pii-production-gate.yml`.
- Fail-closed smoke passed: `scale-tests/runs/20260504-fail-closed-smoke-1`.
- Local production gate passed: `scale-tests/runs/20260504-production-gate-1`.
- Qwen-inclusive production gate passed: `scale-tests/runs/20260504-production-gate-qwen-1`.
- Report updated: `scale-tests/reports/autonomous-pii-experiments-20260503.md`.

## 2026-05-04 API production guardrails

- Added API payload limits with `PIIR_MAX_TEXT_CHARS` and `PIIR_MAX_BATCH_DOCS`.
- Added fail-closed HTTP 503 handling for `PIIExtractionError`.
- Updated `/info` with max text, max batch, auth-required, and fail-closed settings.
- API guardrail smoke passed: `scale-tests/runs/20260504-api-guardrails-smoke-1`.
- CI-style production gate passed after API hardening: `scale-tests/runs/20260504-production-gate-api-hardening-1`.
- Report updated: `scale-tests/reports/autonomous-pii-experiments-20260503.md`.

## 2026-05-04 Deployment hardening checkpoint

- Updated `.env.example` with production settings.
- Updated `docker/docker-compose.yml` with fail-closed/auth/audit/limit/concurrency env vars and healthcheck.
- Updated `docker/Dockerfile` with API healthcheck.
- CI-style production gate passed after deployment hardening: `scale-tests/runs/20260504-production-gate-deploy-hardening-1`.
- Report updated: `scale-tests/reports/autonomous-pii-experiments-20260503.md`.

## 2026-05-04 Production dependency split

- Added `requirements-api.txt`.
- Updated `docker/Dockerfile` to install minimal API/runtime dependencies.
- CI-style production gate passed: `scale-tests/runs/20260504-production-gate-api-req-split-1`.
- Report updated: `scale-tests/reports/autonomous-pii-experiments-20260503.md`.

## 2026-05-04 Docker Compose secret enforcement

- Updated `docker/docker-compose.yml` to require API, re-identification, and audit keys at Compose config time.
- Verified Compose config with dummy secret values.
- Report updated: `scale-tests/reports/autonomous-pii-experiments-20260503.md`.

## 2026-05-04 Final full production gate after hardening

- Final production gate passed: `scale-tests/runs/20260504-production-gate-final-1`.
- Scope: compile integrity, deterministic expanded registry, encrypted audit expanded registry, and real Qwen quick profile.
- Failed checks: 0.
- Report updated: `scale-tests/reports/autonomous-pii-experiments-20260503.md`.

## 2026-05-04 API runtime metrics

- Added authenticated `/metrics` endpoint.
- Metrics smoke passed: `scale-tests/runs/20260504-api-metrics-smoke-1`.
- CI-style production gate passed after metrics: `scale-tests/runs/20260504-production-gate-api-metrics-1`.
- Report updated: `scale-tests/reports/autonomous-pii-experiments-20260503.md`.

## 2026-05-04 Production startup safety enforcement

- Added `PIIR_REQUIRE_PRODUCTION_SAFETY=true`.
- Startup safety smoke passed: `scale-tests/runs/20260504-production-safety-startup-smoke-1`.
- Compose config passed with required dummy secrets.
- CI-style production gate passed: `scale-tests/runs/20260504-production-gate-startup-safety-1`.
- Report updated: `scale-tests/reports/autonomous-pii-experiments-20260503.md`.

## 2026-05-04 Docker image and container smoke

- Docker image build passed: `pii-redactor-api:prod-hardening`.
- Container smoke passed: `scale-tests/runs/20260504-docker-container-smoke-1.json`.
- Validated `/health`, authenticated `/redact`, and authenticated `/metrics`.
- Report updated: `scale-tests/reports/autonomous-pii-experiments-20260503.md`.

## 2026-05-04 Production readiness report

- Added `docs/PRODUCTION_READINESS_REPORT.md`.
- Verdict captured: ready for controlled production pilot after environment-specific secrets/model infrastructure are configured; not a blind broad rollout.
- Report references final production gate and Docker smoke artifacts.
