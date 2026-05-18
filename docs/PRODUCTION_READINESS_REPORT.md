# Production readiness report

Date: 2026-05-04

## Verdict

Ready for a controlled production pilot after environment-specific secrets and
model infrastructure are configured.

Not a blind broad rollout yet. Keep monitoring and manual review active until
real target-document drift is measured.

## Passed gates

- Expanded autonomous deterministic registry: 48,758 documents, 14 fixtures,
  zero failed fixtures.
- Expanded encrypted-audit registry: 48,758 documents, zero plaintext audit
  metadata leaks.
- Real Qwen quick profile over expanded registry: pass.
- Qwen adversarial full run: pass.
- Qwen LLM-only adversarial full run: pass.
- Long-document chunk-boundary Qwen run: pass.
- Async mock and async Qwen checks: pass.
- Audit re-identification round trip: pass.
- Placeholder/result serialization safety: pass.
- API guardrails: auth, text limit, batch limit, and metrics smoke pass.
- Production safety startup enforcement: pass.
- Docker Compose config with required secrets: pass.
- Docker image build: pass.
- Docker container smoke: `/health`, authenticated `/redact`, authenticated
  `/metrics` pass.
- Final production gate with deterministic registry, encrypted audit, compile,
  and real Qwen quick: pass.

## Required production settings

- `PIIR_REQUIRE_PRODUCTION_SAFETY=true`
- `PIIR_REQUIRE_API_KEY=true`
- `PIIR_API_KEY` from a secret manager
- `PIIR_REIDENTIFY_API_KEY` from a separate secret
- `PIIR_AUDIT_KEY` as a Fernet key from a secret manager
- `PIIR_FAIL_ON_LLM_ERROR=true`
- `PIIR_BACKEND=ollama` or `llama_cpp`
- Explicit model URL/name
- Explicit request size, batch size, and concurrency limits

## Known tradeoffs

- Default username detection is high recall and can over-redact technical
  alphanumeric tokens.
- `PIIR_USERNAME_MODE=strict` reduces over-redaction, but is not safe as the
  default because it caused 1,127 scored leaks on the full registry.
- Global local `pip check` reported conflicts from unrelated installed tools;
  production Docker now uses `requirements-api.txt` to avoid demo/test deps.

## Main artifacts

- Production gate script: `scale-tests/run_production_gate.py`
- Expanded registry: `scale-tests/fixtures/registry-autonomous.json`
- Production hardening guide: `docs/PRODUCTION_HARDENING.md`
- KG/RAG firewall guide: `docs/KG_RAG_FIREWALL.md`
- Experiment log: `scale-tests/reports/autonomous-pii-experiments-20260503.md`
- Final full gate: `scale-tests/runs/20260504-production-gate-final-1`
- Docker smoke: `scale-tests/runs/20260504-docker-container-smoke-1.json`

## KG/RAG productization additions

- Product CLI entrypoint: `pii-redactor`
- Policy profiles: `kg_rag_default`, `healthcare_high_recall`, `legal_review`,
  and `logs_low_noise`
- Secure KnowledgeGraph wrapper: `scripts/register-source-secure.ps1`
- Evidence pack generation: `pii-redactor evidence --run <production-gate-run>`
