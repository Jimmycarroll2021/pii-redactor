# Autonomous PII experiment results

- Generated: 2026-05-03T08:38:50.598465+00:00
- Qwen quick run: `scale-tests\runs\20260503-pii-eval-qwen-quick-1` PASS
- Qwen proper run: `scale-tests\runs\20260503-pii-eval-qwen-proper-1` PASS
- Encrypted audit full run: `scale-tests\runs\20260503-pii-eval-encrypted-audit-full-2` PASS
- Encrypted audit documents: 48382
- Encrypted audit failed fixtures: 0

## Encrypted audit fixture results

| Fixture | Documents | Output leaks | Audit plaintext leaks | Encrypted values | Status |
|---|---:|---:|---:|---:|---|
| `ai4privacy-openpii-english-all` | 3923 | 0 | 0 | 28947 | PASS |
| `gretel-pii-masking-en-all` | 4066 | 0 | 0 | 17698 | PASS |
| `kaggle-pii-7k-converted` | 6807 | 0 | 0 | 531264 | PASS |
| `kaggle-pii-diverse-12` | 12 | 0 | 0 | 416 | PASS |
| `pii-context-proof-20260503` | 6 | 0 | 0 | 37 | PASS |
| `pii-hidden-middle-40page-20260503` | 1 | 0 | 0 | 809 | PASS |
| `pii-proof-20260503` | 2 | 0 | 0 | 18 | PASS |
| `synthetic-1000-seed42` | 1000 | 0 | 0 | 16612 | PASS |
| `synthetic-2000-seed43` | 2000 | 0 | 0 | 33251 | PASS |
| `user-openpii-validation-en-all` | 26131 | 0 | 0 | 46915 | PASS |
| `user-pii-dataset-csv-all` | 4434 | 0 | 0 | 146603 | PASS |

## Changes made during autonomous loop

- Tightened benchmark leak checks to ignore volatile `processed_at` in safe result payloads.
- Tightened audit plaintext checks to inspect non-encrypted metadata fields instead of ciphertext/timestamps.
- Expanded deterministic recognizers for email boundaries, usernames in prose/ellipsis contexts, bare domains, and date suffix edge cases.

## Adversarial edge-case experiment

- Generated: 2026-05-03T09:01:37.848906+00:00
- Fixture: `scale-tests/fixtures/adversarial-edgecases-20260503`
- Documents: 120
- Mock run: `scale-tests/runs/20260503-adversarial-edgecases-mock-1` PASS, 0 leaks.
- Encrypted audit run: `scale-tests/runs/20260503-adversarial-edgecases-audit-1` PASS, 0 output leaks, 0 plaintext audit metadata leaks.
- Qwen smoke after Ollama fix: `scale-tests/runs/20260503-adversarial-edgecases-qwen-json-smoke-1` PASS, 0 leaks.
- Qwen full after Ollama fix: `scale-tests\runs\20260503-adversarial-edgecases-qwen-json-full-1` PASS, 120 docs, 0 leaks.
- Qwen throughput on adversarial fixture: 0.120 docs/sec, p95 latency 12467.0 ms.

## Ollama integration fixes

- `OllamaClient` now falls back from `/api/chat` to `/api/generate` for older Ollama servers.
- Ollama calls now request JSON format to reduce malformed model output.
- Config now accepts `OLLAMA_MODEL` and `OLLAMA_HOST` aliases in addition to `PIIR_OLLAMA_MODEL` and `PIIR_OLLAMA_URL`.

## Corrected real-Qwen registry reruns

- Generated: 2026-05-03T09:55:06.882647+00:00
- Model: `qwen2.5:7b` via fixed Ollama native API fallback/JSON mode.
- Quick profile: `scale-tests\runs\20260503-pii-eval-qwen-real-quick-1` PASS, 0 failed fixtures.
- Proper profile: `scale-tests\runs\20260503-pii-eval-qwen-real-proper-1` PASS, 0 failed fixtures.
- This supersedes the earlier Qwen quick/proper evidence that was contaminated by Ollama 404 fallback behavior.

## LLM-only ablation after prompt tightening

- Generated: 2026-05-03T10:26:17.357291+00:00
- Initial LLM-only 24-doc run failed: `scale-tests/runs/20260503-adversarial-edgecases-qwen-llm-only-1`, 5 leaks.
- Prompt tightening run improved but still failed: `scale-tests/runs/20260503-adversarial-edgecases-qwen-llm-only-2`, 3 leaks.
- Final LLM-only full adversarial run passed: `scale-tests\runs\20260503-adversarial-edgecases-qwen-llm-only-full-1`, 120 docs, 0 leaks.
- Reproducible CLI ablation smoke passed: `scale-tests\runs\20260503-adversarial-edgecases-qwen-cli-llm-only-smoke-1`, using `--disable-regex-prepass`.
- Benchmark now records `regex_prepass` in summaries and supports `--disable-regex-prepass`.

## Long-document chunk-boundary experiment

- Generated: 2026-05-03T10:58:54.800950+00:00
- Fixture: `scale-tests/fixtures/longdoc-chunk-boundary-20260503`, 6 docs around 14k characters each.
- Purpose: place name/address/date-of-birth/contact PII near chunk boundaries and in long filler.
- Real Qwen production run: `scale-tests\runs\20260503-longdoc-boundary-qwen-1` PASS, 6 docs, 0 leaks.
- Deterministic focused runs after pattern tuning remained leak-free.
- Full deterministic registry after pattern tuning: `scale-tests\runs\20260503-pii-eval-full-all-data-tight-patterns-2` PASS, failed fixtures: 0.
- Tuning decision: kept high-recall bare username matching because full-registry scored leaks outweighed synthetic filler false positives; tightened generic mixed-ID matching to uppercase-only to remove lowercase filler ID explosions.

## Encrypted audit revalidation after pattern tuning

- Generated: 2026-05-03T11:03:57.346782+00:00
- Run: `scale-tests\runs\20260503-pii-eval-encrypted-audit-full-tight-patterns-1`
- Documents: 48382
- Failed fixtures: 0
- Status: PASS
- Result: 0 output leaks and 0 plaintext audit metadata leaks across the full registry.

## Local model comparison smoke

- Generated: 2026-05-03T11:13:55.818084+00:00
- 7B run: `scale-tests\runs\20260503-adversarial-edgecases-qwen-cli-llm-only-smoke-1`, docs/sec 0.1498, leaks 0.
- 32B run: `scale-tests\runs\20260503-adversarial-edgecases-qwen32b-cli-llm-only-smoke-1`, docs/sec 0.0211, leaks 0.
- Decision: keep `qwen2.5:7b` as the default autonomous experiment model because both passed the adversarial LLM-only smoke, while 32B was materially slower on this machine.

## Benign false-positive / over-redaction experiment

- Generated: 2026-05-03T13:25:37.969830+00:00
- Fixture: `scale-tests/fixtures/benign-false-positive-20260503`, 250 non-PII technical docs.
- Default initial benign run: `scale-tests/runs/20260503-benign-false-positive-mock-1`, username detections 9325, URL detections 400.
- After reserved/test-domain and technical-token suppression: `scale-tests/runs/20260503-benign-false-positive-mock-3`, username detections 6260, URL/generic detections removed.
- Optional strict username mode: `scale-tests\runs\20260503-benign-false-positive-mock-strict-2`, username detections 1600, leaks 0.
- Strict adversarial check: `scale-tests\runs\20260503-adversarial-edgecases-mock-strict-username-2`, leaks 0.
- Default high-recall full registry after tuning: `scale-tests\runs\20260503-pii-eval-full-all-data-fp-tuning-2`, failed fixtures 0.
- Decision: default remains high-recall; `PIIR_USERNAME_MODE=strict` is available for lower over-redaction risk in technical corpora.

## Expanded autonomous regression registry

- Generated: 2026-05-03T13:31:55.917282+00:00
- Registry: `scale-tests/fixtures/registry-autonomous.json`
- Scope: 14 fixture groups, 48,758 documents.
- Deterministic run: `scale-tests\runs\20260503-pii-eval-autonomous-registry-mock-1` PASS, failed fixtures 0.
- Encrypted audit run: `scale-tests\runs\20260503-pii-eval-autonomous-registry-encrypted-audit-1` PASS, failed fixtures 0.
- This registry adds adversarial, benign false-positive, and long-document boundary fixtures to the original full data registry.

## Integrity and expanded-registry Qwen checkpoint

- Generated: 2026-05-03T13:40:55.267425+00:00
- Compile check: `python -m compileall -q pii_redactor scale-tests` PASS.
- Real Qwen quick expanded-registry run: `scale-tests\runs\20260503-pii-eval-autonomous-registry-qwen-quick-1` PASS, failed fixtures 0.

## Async pipeline concurrency checks

- Generated: 2026-05-03T13:42:20.665764+00:00
- Async mock concurrency-16 run: `scale-tests\runs\20260503-adversarial-async-mock-1` PASS, 120 docs, 0 leaks, 1512.03 docs/sec.
- Async Qwen concurrency-2 run: `scale-tests\runs\20260503-adversarial-async-qwen-1` PASS, 8 docs, 0 leaks, 0.184 docs/sec.
- Purpose: verify `process_document_async` preserves redaction correctness under concurrent calls.

## Audit and safe serialization checks

- Generated: 2026-05-03T13:42:51.339516+00:00
- Audit re-identification round trip: `scale-tests\runs\20260503-audit-reidentify-roundtrip-1` PASS; entries 3; plaintext leaks 0; without-key reidentify fails: True.
- Placeholder serialization safety: `scale-tests\runs\20260503-placeholder-safety-1` PASS; repeated email placeholder consistent: True; repeated phone placeholder consistent: True; raw leaks 0.

## Strict username full-registry tradeoff

- Generated: 2026-05-03T13:44:36.708887+00:00
- Run: `scale-tests\runs\20260503-pii-eval-full-strict-username-tradeoff-1` FAIL.
- Failed fixtures: 4.
- Total strict-mode scored leaks: 1127.
- Main leak source: bare username values in AI4Privacy, Gretel, Kaggle, and user CSV data.
- Decision: `PIIR_USERNAME_MODE=strict` remains opt-in only; default high-recall mode is required for leak prevention.

## 2026-05-04 production hardening checkpoint

- Generated: 2026-05-03T20:57:40.674568+00:00
- Added fail-closed extraction mode: `PIIR_FAIL_ON_LLM_ERROR=true`.
- Added production gate runner: `scale-tests/run_production_gate.py`.
- Added production hardening guide: `docs/PRODUCTION_HARDENING.md`.
- Added CI workflow scaffold: `.github/workflows/pii-production-gate.yml`.
- Fail-closed smoke: `scale-tests\runs\20260504-fail-closed-smoke-1` PASS.
- Local production gate: `scale-tests\runs\20260504-production-gate-1` PASS, failed checks 0.
- Qwen-inclusive production gate: `scale-tests\runs\20260504-production-gate-qwen-1` PASS, failed checks 0.

## 2026-05-04 API production guardrails

- Generated: 2026-05-03T21:00:05.463427+00:00
- Added API text and batch size limits: `PIIR_MAX_TEXT_CHARS`, `PIIR_MAX_BATCH_DOCS`.
- Added HTTP 503 mapping for fail-closed `PIIExtractionError`.
- `/info` now exposes production-relevant limits and fail-closed/auth settings.
- API guardrail smoke: `scale-tests\runs\20260504-api-guardrails-smoke-1` PASS.
- CI-style production gate after API hardening: `scale-tests\runs\20260504-production-gate-api-hardening-1` PASS, failed checks 0.

## 2026-05-04 deployment hardening checkpoint

- Generated: 2026-05-03T21:02:07.248435+00:00
- Updated `.env.example` with production auth, limits, fail-closed, and Ollama settings.
- Updated Docker Compose to require API key, fail closed on LLM errors, set audit/limit/concurrency env vars, and expose a service healthcheck.
- Added Dockerfile healthcheck for `/health`.
- Compile check after deployment hardening: PASS.
- CI-style production gate: `scale-tests\runs\20260504-production-gate-deploy-hardening-1` PASS, failed checks 0.

## 2026-05-04 production dependency split

- Generated: 2026-05-03T21:04:10.687787+00:00
- Added `requirements-api.txt` for minimal production API/container dependencies.
- Updated Dockerfile to use `requirements-api.txt` instead of demo/test-heavy `requirements.txt`.
- Noted global `pip check` conflicts are from the shared Python environment and unrelated installed tools; production image should use the minimal API requirements.
- CI-style production gate after dependency split: `scale-tests\runs\20260504-production-gate-api-req-split-1` PASS, failed checks 0.

## 2026-05-04 Docker Compose secret enforcement

- Generated: 2026-05-03T21:04:48.020476+00:00
- Updated `docker/docker-compose.yml` to require `PIIR_API_KEY`, `PIIR_REIDENTIFY_API_KEY`, and `PIIR_AUDIT_KEY` using Compose required-variable syntax.
- Verified `docker compose -f docker/docker-compose.yml config` succeeds with dummy secret values.
- This prevents production containers from starting with blank authentication or audit keys.

## 2026-05-04 final full production gate after hardening

- Generated: 2026-05-03T21:20:41.116696+00:00
- Run: `scale-tests\runs\20260504-production-gate-final-1`
- Status: PASS
- Failed checks: 0
- Scope: compile integrity, deterministic expanded registry, encrypted audit expanded registry, and real Qwen quick profile.

## 2026-05-04 API runtime metrics

- Generated: 2026-05-03T21:22:47.086210+00:00
- Added authenticated `/metrics` endpoint with documents, spans, errors, latency, and category counters.
- Metrics smoke: `scale-tests\runs\20260504-api-metrics-smoke-1` PASS.
- CI-style production gate after metrics: `scale-tests\runs\20260504-production-gate-api-metrics-1` PASS, failed checks 0.

## 2026-05-04 production startup safety enforcement

- Generated: 2026-05-03T21:24:57.950923+00:00
- Added `PIIR_REQUIRE_PRODUCTION_SAFETY=true` startup enforcement.
- API startup now fails if API key, re-identification key, audit key, or fail-closed mode is missing.
- Docker Compose sets `PIIR_REQUIRE_PRODUCTION_SAFETY=true`.
- Startup safety smoke: `scale-tests\runs\20260504-production-safety-startup-smoke-1` PASS.
- Compose config with dummy required secrets: `scale-tests/runs/20260504-compose-config-production-safety-1.txt` PASS.
- CI-style production gate: `scale-tests\runs\20260504-production-gate-startup-safety-1` PASS, failed checks 0.

## 2026-05-04 Docker image and container smoke

- Generated: 2026-05-03T21:33:23.752334+00:00
- Docker image build passed: `pii-redactor-api:prod-hardening`.
- Container smoke: `scale-tests\runs\20260504-docker-container-smoke-1.json` PASS.
- Checked `/health`, authenticated `/redact`, and authenticated `/metrics` from the running container.
- Smoke result: pii_count 2, documents_processed 1, pii_spans_total 2.
## 2026-05-04 KG/RAG firewall productization

- Added policy profiles in `pii_redactor/policies.py`.
- Added CLI entrypoint `pii-redactor` with `redact`, `ingest`, `gate`, and `evidence` commands.
- Added `docs/KG_RAG_FIREWALL.md`.
- Added secure KnowledgeGraph registration wrapper at `C:\Users\j_car\KnowledgeGraph\scripts\register-source-secure.ps1`.
- Extended production gate to emit evidence packs through the CLI.
- Updated readiness report with KG/RAG firewall productization artifacts.
