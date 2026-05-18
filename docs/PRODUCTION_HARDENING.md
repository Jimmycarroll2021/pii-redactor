# Production hardening guide

This project has strong local evidence for PII leak prevention, but production
use should be gated by repeatable checks and fail-closed runtime settings.

## Required production environment

Set these explicitly in production:

```powershell
$env:PIIR_BACKEND = "ollama"
$env:PIIR_OLLAMA_MODEL = "qwen2.5:7b"
$env:PIIR_OLLAMA_URL = "http://127.0.0.1:11434"
$env:PIIR_FAIL_ON_LLM_ERROR = "true"
$env:PIIR_REQUIRE_PRODUCTION_SAFETY = "true"
$env:PIIR_REQUIRE_API_KEY = "true"
$env:PIIR_API_KEY = "<redaction-api-key-from-secret-manager>"
$env:PIIR_REIDENTIFY_API_KEY = "<separate-reidentify-key-from-secret-manager>"
$env:PIIR_MAX_TEXT_CHARS = "200000"
$env:PIIR_MAX_BATCH_DOCS = "1000"
$env:PIIR_MAX_CONCURRENCY = "8"
$env:PIIR_AUDIT_ENABLED = "true"
$env:PIIR_AUDIT_PATH = "C:\secure-audit\pii-audit.jsonl"
$env:PIIR_AUDIT_KEY = "<fernet-key-from-secret-manager>"
```

`PIIR_FAIL_ON_LLM_ERROR=true` is the production safety switch. If the model
backend fails or returns malformed JSON, processing raises an error instead of
silently returning a regex-only redaction.

`PIIR_REQUIRE_PRODUCTION_SAFETY=true` makes the API fail startup if required
production controls are missing.

## Production gate

Run the full local gate before deployment:

```powershell
python scale-tests\run_production_gate.py --registry scale-tests\fixtures\registry-autonomous.json --out scale-tests\runs\production-gate
```

Add `--include-ollama` when the local model server is available:

```powershell
python scale-tests\run_production_gate.py --registry scale-tests\fixtures\registry-autonomous.json --include-ollama --ollama-model qwen2.5:7b --out scale-tests\runs\production-gate-qwen
```

The gate checks:

- Python compile integrity.
- Deterministic leak regression over the autonomous registry.
- Encrypted audit regression with plaintext-leak checks.
- Optional real Qwen quick profile.

## Production dependencies

The Docker API image uses `requirements-api.txt`, not `requirements.txt`.
`requirements.txt` includes demo/test dependencies such as Gradio and pytest;
`requirements-api.txt` keeps the production service smaller and avoids unrelated
demo dependency conflicts.

## Current deployment verdict

The system is ready for controlled pilot use after the production gate passes
in the target environment. For broad production, add service-level controls:

- API authentication and authorization.
- Input size limits and request timeouts.
- Rate limits and concurrency caps.
- Audit key storage in a secret manager.
- Audit log retention policy.
- Monitoring for latency, model failures, detection-count spikes, and audit
  write failures.
- Manual review path for over-redaction and re-identification requests.

## Runtime metrics

The API exposes authenticated JSON metrics at `GET /metrics`.

Tracked fields include:

- `documents_processed`
- `pii_spans_total`
- `errors_total`
- `latency_ms_mean`
- `latency_ms_max`
- per-category detection counts under `categories`

Use these for alerting on model failures, latency spikes, unexpected detection
volume changes, and sudden category distribution shifts.
