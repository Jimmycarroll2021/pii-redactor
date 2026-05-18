# Production Operator Checklist

Use this checklist before running the PII Redactor as a KG/RAG ingestion firewall in a regulated environment.

## Required Configuration

- `PIIR_REQUIRE_API_KEY=true`
- `PIIR_REQUIRE_PRODUCTION_SAFETY=true`
- `PIIR_BACKEND=ollama`, `llama_cpp`, or `hf`
- `PIIR_BACKEND` is not `mock`
- `PIIR_API_KEY` is set
- `PIIR_REIDENTIFY_API_KEY` is set and differs from `PIIR_API_KEY`
- `PIIR_AUDIT_KEY` is set
- `PIIR_FAIL_ON_LLM_ERROR=true`
- `PIIR_MAX_TEXT_CHARS` is set for the deployment tier
- `PIIR_MAX_BATCH_DOCS` is set for the deployment tier

## Model Controls

- Confirm `model_used` from `/redact` is the intended model.
- For this machine, current validated local model is `qwen2.5:7b`.
- Keep Qwen/Ollama timeout high enough for long documents: `PIIR_LLM_TIMEOUT_SECONDS=600`.
- Use deterministic temperature for audit reproducibility.

## Audit Controls

- Store `PIIR_AUDIT_KEY` outside source control.
- Rotate `PIIR_AUDIT_KEY` through a documented break-glass process.
- Restrict `/reidentify` to caseworker or administrator roles only.
- Use a separate `PIIR_REIDENTIFY_API_KEY`; do not reuse the redaction API key.
- Review audit-log storage location before pilot ingestion.

## KG/RAG Ingestion Controls

- Raw sources go to `raw/incoming` or another non-ingestion staging area.
- KG/RAG ingestion consumes only `raw/redacted` outputs.
- Use `scripts/register-source-secure.ps1` for source registration by default.
- Direct `scripts/register-source.ps1` raw registration requires explicit `-AllowRaw`.
- Keep PII manifests under `manifests/pii-redaction`.

## Pre-Pilot Gates

- Full production gate passes.
- Encrypted audit gate passes.
- Qwen/Ollama quick gate passes if using Ollama.
- Docker image builds.
- Docker production-safety mock refusal passes.
- Docker real-backend API smoke passes.
- Secure KnowledgeGraph wrapper smoke passes.

Latest passing validation record:

- `docs/KG_RAG_PRODUCTIZATION_VALIDATION_20260504.md`

## Pilot Exit Criteria

- Zero known plaintext PII leaks in redacted outputs.
- Audit metadata contains no plaintext original values.
- Re-identification works only with the audit key and re-identification credential.
- Operators can reproduce evidence packs from run directories.
- Any failed ingestion fails closed before graph/vector ingestion.
