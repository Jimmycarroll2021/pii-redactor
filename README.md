# PII Redactor

Pre-ingestion PII de-identification for Australian government data.

Implements the methodology from Wiest et al., *Deidentifying Medical Documents with Local, Privacy-Preserving Large Language Models* (NEJM AI, 2024), extended with Australian Commonwealth identifier detection and checksum validation.

[![Tests](https://img.shields.io/badge/tests-137%2F137%20passing-brightgreen)](#testing)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](#)
[![License](https://img.shields.io/badge/license-MIT-green)](#)
[![HF Hub](https://img.shields.io/badge/HF%20Hub-redact--au--1b-yellow)](https://huggingface.co/JimmyBhoy/redact-au-1b)

> **v0.4.1 — AU organisation + location recognisers (2026-05-20).** Per-sector
> sensitivity lift +0.64 to +6.76 pp across federal/state-health/legal/medtech
> benches; organisation per-category recall +13-56 pp; location +33 pp on
> federal. Frozen Wiest bench held exactly (Medical 99.71%/0 leaks, Gretel
> 93.67%/2 leaks). The companion LoRA adapter
> [`JimmyBhoy/redact-au-1b`](https://huggingface.co/JimmyBhoy/redact-au-1b)
> ships on HF Hub (apache-2.0) for the two-tier AU-government + clinical
> deployment path. See `CHANGELOG.md` for the full v0.4.1 changeset.

## What it does

Sits between a data source and an ingestion target in your pipeline. Documents come in containing PII; documents go out with PII replaced by structured placeholders. Original values live only in an encrypted audit log, recoverable by audit ID with the right key.

```
   Source → [PII Redactor] → Ingestion target (warehouse, search, model training, ...)
                ↓
        encrypted audit log
```

## Why this design

Four things make this approach work for production AU government + clinical workloads:

1. **LoRA-tuned token classifier on `openai/privacy-filter`** (the default in v0.4.x). 1.5B-param / 50M-active MoE token classifier, fine-tuned on a ~55k-doc AU-synthetic corpus covering all 11 AU regulatory categories. Wiest-equivalent recall on AU clinical narratives with 5-6 docs/sec inference on a single RTX 4090. The LoRA adapter is published separately at [`JimmyBhoy/redact-au-1b`](https://huggingface.co/JimmyBhoy/redact-au-1b) (Apache 2.0).
2. **Two-tier product.** Default tier (Tier 1) drops the slow narrative-NER pass for ≥3 d/s throughput on AU compliance workloads. Opt-in Tier 2 (`PIIR_LLAMA_BACKEND=vllm`) layers a Llama-3.1-8B narrative pass on top for general-PII workloads at lower throughput but higher recall on non-AU formats.
3. **Local inference.** No data leaves your boundary. Important for OFFICIAL / OFFICIAL: Sensitive deployments. PROTECTED requires IRAP (see `grants/IRAP-scoping.md` in the companion `redact-au` repo for the assessment path).
4. **Australian checksum validation** (our addition). The token classifier is tuned for recall; downstream validators add precision. A nine-digit number that looks like a TFN but fails the mod-11 weighted sum gets dropped. Same for ABN (mod-89), ACN, Medicare. This filters most false positives on numeric identifiers.

## Detected categories

| Category | Validation | Notes |
|----------|-----------|-------|
| `name` | none | Personal names of individuals |
| `address` | none | Postal or street addresses |
| `patient_id` | context-bound regex + LLM | Labelled patient identifiers |
| `medical_record_number` | context-bound regex + LLM | MRN, URN, hospital number |
| `healthcare_identifier` | context-bound regex + LLM | IHI or labelled healthcare identifier |
| `date_of_birth` | none | Distinguished from generic dates by context |
| `date` | none | Other dates |
| `phone` | regex format | AU mobile and landline formats |
| `email` | regex format | RFC 5322 simplified |
| `tfn` | **mod-11 checksum** | 8 or 9 digits, ATO algorithm |
| `medicare` | **checksum** | 10 or 11 digits, includes IRN handling |
| `abn` | **mod-89 checksum** | 11 digits, ATO algorithm |
| `acn` | **checksum** | 9 digits, ASIC algorithm |
| `driver_licence` | none | State-specific formats |
| `passport` | none | Australian passport pattern |
| `bsb_account` | format | 6-digit BSB + account |
| `centrelink_crn` | none | Customer Reference Number |
| `organisation` | gazetteer + suffix pattern | Companies (Pty Ltd, Limited), gov agencies, hospitals, universities, banks, law firms (v0.4.1+) |
| `location` | gazetteer + state-abbrev + postcode | Suburbs, states, postcodes, regions — standalone references (v0.4.1+) |
| `url`, `ip_address` | regex | Standard formats |

Validators that exist will drop invalid detections from the output. The validation result is preserved on each span so downstream consumers can see what was confirmed vs. flagged.

## Measured performance (2026-05-20)

**v0.4.1 frozen bench — RTX 4090, concurrent×8 HTTP:**

| Fixture | Tier 1 (default, LoRA, llama off) | Tier 2 (opt-in, +llama vLLM) | Legacy CPU baseline (v0.1.2 Ollama) |
|---|---|---|---|
| Gretel-100 sensitivity | **93.67%** (2 leaks) | **97.89%** (0 leaks) | **99.58%** (1 leak) |
| Medical-50 sensitivity | **99.71%** (0 leaks) | **100.00%** (0 leaks) | **100.00%** (0 leaks) |
| Throughput (docs/sec) | **5-6** | 1.4 | 0.07 |
| Mean latency / doc | ~150-300 ms | ~700 ms | 13.8-20.4 s |
| Hardware | RTX 4090 (24 GB) | RTX 4090 + vLLM | Ryzen 7 7840HS CPU |

All three tiers clear the Wiest et al. 99.4% sensitivity bar on the medical fixture (Wiest target = 99.4%; we hit 99.71% / 100% / 100%). The Gretel-100 fixture covers global+social PII broader than our AU-government wedge — Tier 2 closes that gap when the workload includes international phone formats, social handles, or foreign locality names.

**Multi-sector v0.4.1 head-to-head** (920 docs across federal-gov / state-health / legal / medtech, vs Microsoft Presidio):

| Sector | redact-au v0.4.1 (Tier 1) | Microsoft Presidio + AU regex | Δ |
|---|---|---|---|
| federal-gov-official | **93.15%** | 78.32% | **+14.83 pp** |
| state-health-hospitals | **93.55%** | 86.05% | **+7.50 pp** |
| legal-small-mid | **85.75%** | 69.92% | **+15.83 pp** |
| medtech-health-ai | **91.57%** | 77.72% | **+13.85 pp** |

100% recall on AU regulatory IDs (TFN/ABN/ACN/Medicare/IHI/MRN/BSB/Centrelink-CRN) with checksum validation across all four sectors. Per-category breakdown + leak taxonomy in the companion `redact-au` repo's `benchmarks/` directory.

Per-leak diagnostics, severity grading, and full per-category recall are in `CHANGELOG.md` (v0.4.0 + v0.4.1) and the v0.0.x → v0.4.1 history under `.planning/`.

## Three integration paths

### 1. Python library (recommended for in-process pipelines)

```bash
# From PyPI
pip install pii-redactor-au

# Or editable from source
pip install -e .
```

The PyPI **distribution name** is `pii-redactor-au` (the unqualified `pii-redactor` is owned by another project). The **import name remains `pii_redactor`** — no code change for consumers.

```python
from pii_redactor import build_pipeline

pipeline = build_pipeline()  # reads config from env
result = pipeline.process_document(text)

print(result.redacted_text)
print(f"Found {result.pii_count} PII items")
print(result.pii_table())  # safe extracted-PII table, no original values
print(f"Audit ID: {result.audit_id}")
```

### 2. FastAPI service (for cross-language pipelines)

```bash
docker compose -f docker/docker-compose.yml up -d
curl localhost:8000/health
```

```bash
curl -X POST localhost:8000/redact \
  -H "X-API-Key: $PIIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": "TFN: 123 456 782, contact: jdoe@example.com"}'
```

Endpoints:

- `POST /redact` — single document
- `POST /redact/batch` — list of documents
- `POST /reidentify` — recover original values from audit_id (requires audit key)
- `GET /health`, `GET /info`

### 3. Gradio Space (for demo and stakeholder review)

```bash
python app.py
# or push to HF Spaces with HF_TOKEN set as a Space secret
```

The Space uses HF Inference API as the backend so it works without llama.cpp. Same library, thin UI wrapper.

## Configuration

All configuration via environment variables prefixed `PIIR_`. See `.env.example` for the full list. Key ones:

| Variable | Default | Purpose |
|----------|---------|---------|
| `PIIR_BACKEND` | `transformers_au_finetuned` | `mock` \| `llama_cpp` \| `hf` \| `ollama` \| `transformers_au` \| `transformers_au_finetuned` |
| `PIIR_LORA_ADAPTER` | `JimmyBhoy/redact-au-1b` | HF Hub repo or local path to LoRA adapter (only for `transformers_au_finetuned`) |
| `PIIR_LLAMA_BACKEND` | `disabled` | `disabled` \| `vllm` \| `ollama` \| `auto` — Tier 2 narrative-NER pass |
| `PIIR_LLAMA_GATE` | `always` | `always` \| `confidence` \| `never` — when Tier 2 is enabled, gate per-doc |
| `PIIR_VLLM_URL` | `http://localhost:11500` | vLLM OpenAI-compatible endpoint |
| `PIIR_OLLAMA_URL` | `http://localhost:11434` | Ollama server endpoint |
| `PIIR_LLAMA_CPP_URL` | `http://localhost:8080` | llama.cpp server endpoint |
| `PIIR_HF_TOKEN` | — | HF Inference API token (for `hf` backend) |
| `PIIR_REGEX_USERNAME` | `false` | Toggle username regex (off by default — false positives risk) |
| `PIIR_REGEX_ORGANISATION` | `true` | Toggle organisation gazetteer + suffix recogniser (v0.4.1+) |
| `PIIR_REGEX_LOCATION` | `true` | Toggle location gazetteer + state/postcode recogniser (v0.4.1+) |
| `PIIR_API_KEY` | — | FastAPI auth (unset = open) |
| `PIIR_AUDIT_KEY` | — | Fernet key for audit encryption |
| `PIIR_PLACEHOLDER_STYLE` | `numbered` | `numbered` \| `category` \| `asterisk` |

Generate keys:

```bash
# API key (for X-API-Key header)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Audit encryption key (Fernet)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Audit and re-identification

Every detection is written to an encrypted JSONL audit log:

```json
{
  "audit_id": "uuid",
  "document_id": "uuid",
  "timestamp": "...",
  "category": "tfn",
  "span_start": 14,
  "span_end": 25,
  "value_encrypted": "gAAAAAB...",
  "placeholder": "[REDACTED_TFN_001]",
  "confidence": 1.0,
  "validator_passed": true,
  "model_used": "llama-3-8b-instruct"
}
```

With the audit key, an authorised caller can recover originals:

```python
originals = pipeline.audit.reidentify(audit_id)
# → list of dicts including the decrypted `value`
```

If no audit key is configured, the log records that PII was detected and what category, but not the values. We refuse to write plaintext PII to the audit log under any circumstances. This is a deliberate fail-safe.

## Privacy Act 1988 alignment

Three properties of this design that map to APP obligations:

- **APP 11 (security).** Original values are encrypted at rest in the audit log. AES-128-CBC + HMAC via Fernet. Re-identification requires the key, which is held outside the redactor.
- **APP 11.2 (destruction).** Setting `PIIR_AUDIT_ENABLED=false` disables logging entirely. Spans returned downstream never carry original values regardless of audit configuration.
- **APP 12 (access and correction).** The `audit_id` returned with every redaction lets a data subject's request be linked back to specific source documents.

This is not a substitute for a legal review. It's infrastructure that makes APP-aligned operation tractable.

## Testing

```bash
pytest tests/ -v
```

Current state: **137 tests, all passing** (v0.4.1). Validators exercised against published test values from ATO (TFN, ABN), ASIC (ACN), and synthetically valid Medicare numbers. Pipeline tests use the `MockClient` backend (regex-only) so they run offline without an LLM. Regression coverage spans every release: v0.1.x phone/BSB/ABN edge cases, v0.2.x hybrid pipeline integration, v0.3.x vLLM + concurrency, v0.4.x LoRA backend + org/location recognisers + llama-disabled default + fallback-chain.

## Architecture

```
pii_redactor/
├── models.py                # PIICategory (+ ORGANISATION, LOCATION since v0.4.1), PIISpan, RedactionResult
├── validators.py            # AU checksum algorithms (TFN, ABN, ACN, Medicare)
├── prompts.py               # Zero-shot prompt templates (legacy llama path)
├── grammar.py               # GBNF grammar for llama.cpp constrained sampling
├── llm_client.py            # Backends: LlamaCpp, HFInference, Ollama, Mock
├── detector.py              # chunk → prompt → parse → validate → merge
├── redactor.py              # Apply placeholders, three styles
├── audit.py                 # Fernet-encrypted JSONL audit
├── pipeline.py              # Public API: build_pipeline(), process_document()
├── config.py                # env-driven Pydantic settings
├── data/gazetteers/         # AU org + suburb + postcode + state gazetteers (v0.4.1+)
└── hybrid/                  # Hybrid pipeline (v0.2.x+)
    ├── openai_backend.py    # openai/privacy-filter token-classifier wrapper
    ├── finetuned_backend.py # PEFT-loaded LoRA adapter on openai/privacy-filter (v0.4.x+)
    ├── llama_pass.py        # Ollama Llama-3.1-8B narrative pass (Tier 2)
    ├── vllm_pass.py         # vLLM AWQ-Marlin narrative pass (Tier 2, RTX)
    ├── au_resolver.py       # Checksum + label-prior resolution for AU IDs
    ├── au_org_loc.py        # Organisation + location recognisers (v0.4.1+)
    ├── regex_supplement.py  # Username + AU phone/address fallback
    └── pipeline.py          # HybridDetector orchestrator + tier selection

api/main.py                  # FastAPI HTTP service
app.py                       # Gradio Space entry point
tests/                       # Pytest suite (137 tests as of v0.4.1)
docker/                      # Dockerfile + compose stack
```

## Source

Wiest IC, Leßmann ME, Wolf F, et al. *Deidentifying Medical Documents with Local, Privacy-Preserving Large Language Models: The LLM-Anonymizer.* NEJM AI 2024. DOI: [10.1056/AIdbp2400537](https://ai.nejm.org/doi/full/10.1056/AIdbp2400537)

## License

MIT

## Local project consolidation

This source checkout is now consolidated under `C:\Users\j_car\.00xxAIProjectsxx00\Redact-au\libs\pii-redactor`.

Related reference material is kept in `docs/references/`, including the NEJM AI LLM-Anonymizer paper used to ground the de-identification design.
