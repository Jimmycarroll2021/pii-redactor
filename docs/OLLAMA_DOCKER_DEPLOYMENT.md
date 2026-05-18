# Ollama Docker Deployment Guide

This guide runs the PII Redactor API as a Docker container while using a real local Ollama model, such as `qwen2.5:7b`, for LLM-backed entity extraction.

## Required Posture

Production-like deployments must not use the mock backend.

Required settings:

```powershell
$env:PIIR_API_KEY = "<redaction-api-key>"
$env:PIIR_REIDENTIFY_API_KEY = "<separate-reidentify-key>"
$env:PIIR_AUDIT_KEY = "<fernet-compatible-audit-key>"
$env:PIIR_REQUIRE_API_KEY = "true"
$env:PIIR_REQUIRE_PRODUCTION_SAFETY = "true"
$env:PIIR_BACKEND = "ollama"
$env:PIIR_OLLAMA_MODEL = "qwen2.5:7b"
$env:PIIR_OLLAMA_URL = "http://host.docker.internal:11434"
$env:PIIR_FAIL_ON_LLM_ERROR = "true"
```

`PIIR_REQUIRE_PRODUCTION_SAFETY=true` now refuses to start if `PIIR_BACKEND=mock`.

## Build

```powershell
Set-Location C:\Users\j_car\KnowledgeGraph\tools\pii-redactor
docker build -f docker\Dockerfile -t pii-redactor-api:kg-rag-productization .
```

## Run

```powershell
docker run -d --name pii-redactor-api `
  -p 8000:8000 `
  -e PIIR_REQUIRE_API_KEY=true `
  -e PIIR_REQUIRE_PRODUCTION_SAFETY=true `
  -e PIIR_API_KEY=$env:PIIR_API_KEY `
  -e PIIR_REIDENTIFY_API_KEY=$env:PIIR_REIDENTIFY_API_KEY `
  -e PIIR_AUDIT_KEY=$env:PIIR_AUDIT_KEY `
  -e PIIR_BACKEND=ollama `
  -e PIIR_OLLAMA_URL=http://host.docker.internal:11434 `
  -e PIIR_OLLAMA_MODEL=qwen2.5:7b `
  -e PIIR_LLM_TIMEOUT_SECONDS=600 `
  -e PIIR_LLM_RETRIES=1 `
  pii-redactor-api:kg-rag-productization
```

## Smoke Test

```powershell
$headers = @{ "X-API-Key" = $env:PIIR_API_KEY }

Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"

$body = @{
  document_id = "smoke-001"
  text = "Patient Jane Citizen email jane.citizen@example.com phone 0412 345 678 Medicare 2123 45670 1"
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/redact" `
  -Method Post `
  -Headers $headers `
  -ContentType "application/json" `
  -Body $body

Invoke-RestMethod -Uri "http://127.0.0.1:8000/metrics" -Headers $headers
```

Expected result:

- `/health` returns `status=ok`.
- `/redact` removes name, email, phone, and Medicare-like identifier.
- `/metrics` increments `documents_processed` and category counters.
- `model_used` is `qwen2.5:7b`, not `mock`.

## KnowledgeGraph Secure Ingestion

Use the secure wrapper instead of direct source registration when source material may contain PII:

```powershell
Set-Location C:\Users\j_car\KnowledgeGraph

$env:PIIR_BACKEND = "ollama"
$env:PIIR_OLLAMA_URL = "http://127.0.0.1:11434"
$env:PIIR_OLLAMA_MODEL = "qwen2.5:7b"
$env:PIIR_LLM_TIMEOUT_SECONDS = "600"
$env:PIIR_LLM_RETRIES = "1"

.\scripts\register-source-secure.ps1 `
  -Path ".\raw\incoming\source.txt" `
  -Title "Source Title" `
  -SourceType "other" `
  -Policy "kg_rag_default"
```

The wrapper writes:

- Redacted source under `raw/redacted`.
- PII manifest under `manifests/pii-redaction`.
- Source registry row pointing to the redacted path only.

Direct `scripts/register-source.ps1` now accepts redacted paths by default. Registering raw, non-redacted paths requires `-AllowRaw` and should be reserved for explicitly reviewed non-PII sources.

## Operational Notes

- Keep raw files out of graph/vector ingestion paths.
- Use `register-source-secure.ps1` for KG/RAG sources by default.
- Keep `PIIR_AUDIT_KEY` separate from API keys.
- Use a separate `PIIR_REIDENTIFY_API_KEY`; do not reuse the redaction API key for caseworker re-identification.
- Treat `mock` as test-only. It is blocked by production safety mode.
