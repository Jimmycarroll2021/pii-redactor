# PII Redactor

Pre-ingestion PII de-identification for Australian government data.

Implements the methodology from Wiest et al., *Deidentifying Medical Documents with Local, Privacy-Preserving Large Language Models* (NEJM AI, 2024), extended with Australian Commonwealth identifier detection and checksum validation.

[![Tests](https://img.shields.io/badge/tests-38%2F38%20passing-brightgreen)](#testing)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](#)
[![License](https://img.shields.io/badge/license-MIT-green)](#)

## What it does

Sits between a data source and an ingestion target in your pipeline. Documents come in containing PII; documents go out with PII replaced by structured placeholders. Original values live only in an encrypted audit log, recoverable by audit ID with the right key.

```
   Source → [PII Redactor] → Ingestion target (warehouse, search, model training, ...)
                ↓
        encrypted audit log
```

## Why this design

Three things from the paper that make the approach work, and one we added:

1. **Zero-shot LLM detection.** Measured on this codebase (2026-05-18): Llama-3.1-8B-Instruct via Ollama hits **99.58% sensitivity on the 100-doc Gretel PII fixture** (1 name leak / 237 checked) and **100.00% sensitivity on the 50-doc synthetic medical fixture** (0 leaks / 345 checked, all 9 categories at 100% recall). See `.planning/PASS-GATE.md` for run details and per-category breakdown. Wiest et al. reported 99.4% sensitivity on Llama-3-8B for the LLM-Anonymizer paper; this fork meets or beats that bar on both AU-government and synthetic-medical fixtures.
2. **Grammar-constrained output.** llama.cpp's GBNF support means the model literally cannot emit malformed JSON. No `try/except json.JSONDecodeError` paranoia.
3. **Local inference.** No data leaves your boundary. Important for OFFICIAL: Sensitive and PROTECTED data.
4. **Australian checksum validation** (our addition). The LLM is tuned for recall; checksum validators add precision. A nine-digit number that looks like a TFN but fails the mod-11 weighted sum gets dropped. This filters most LLM false positives on numeric identifiers.

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
| `url`, `ip_address` | regex | Standard formats |

Validators that exist will drop invalid detections from the output. The validation result is preserved on each span so downstream consumers can see what was confirmed vs. flagged.

## Measured performance (2026-05-18)

| Fixture | Model | Backend | Docs | Sensitivity | Leaks |
|---------|-------|---------|------|-------------|-------|
| Gretel-100 (`gretel-pii-masking-en-500`, first 100) | `llama3.1:8b` (Q4_K_M) | Ollama, CPU | 100 | **99.58%** | 1 / 237 (1 name) |
| Synthetic-medical-50 (`synthetic-medical-50`) | `llama3.1:8b` (Q4_K_M) | Ollama, CPU | 50 | **100.00%** | 0 / 345 |

Both numbers clear the Wiest et al. 99.4% sensitivity bar. Full per-category recall, raw `summary.json`, and `results.jsonl` files are committed under `scale-tests/runs/20260518-us003b-ollama-llama31-gretel100-prompt-v3/` and `scale-tests/runs/20260518-us006-ollama-llama31-medical50/`. The reproducible synthetic-medical fixture generator lives at `scale-tests/generate_synthetic_medical.py` (seeded; 0 spend; 15 / 50 documents include Medicare or IHI to stay within product scope).

Hardware: AMD Ryzen 7 7840HS, CPU-only inference. Mean latency 13.8 s/doc (Gretel) and 20.4 s/doc (medical narratives). The pass gate, model selection, prompt edits, and per-leak diagnostics are written up in `.planning/PASS-GATE.md`.

## Three integration paths

### 1. Python library (recommended for in-process pipelines)

```bash
pip install -e .
```

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
| `PIIR_BACKEND` | `mock` | `mock` \| `llama_cpp` \| `hf` \| `ollama` |
| `PIIR_LLAMA_CPP_URL` | `http://localhost:8080` | llama.cpp server endpoint |
| `PIIR_HF_TOKEN` | — | HF Inference API token |
| `PIIR_OLLAMA_URL` | `http://localhost:11434` | Ollama server endpoint |
| `PIIR_OLLAMA_MODEL` | `llama3` | Ollama model name (must be pulled first) |
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

Current state: 38 tests, all passing. Validators exercised against published test values from ATO (TFN, ABN), ASIC (ACN), and synthetically valid Medicare numbers. Pipeline tests use the `MockClient` backend (regex-only) so they run offline without an LLM. Regression tests cover all three bugs fixed in v0.1.1 (phone format, BSB false positives, phone-in-ABN).

## Architecture

```
pii_redactor/
├── models.py        # PIICategory, PIISpan, RedactionResult
├── validators.py    # AU checksum algorithms (TFN, ABN, ACN, Medicare)
├── prompts.py       # Zero-shot prompt templates
├── grammar.py       # GBNF grammar for llama.cpp constrained sampling
├── llm_client.py    # Backends: LlamaCpp, HFInference, Ollama, Mock
├── detector.py      # chunk → prompt → parse → validate → merge
├── redactor.py      # Apply placeholders, three styles
├── audit.py         # Fernet-encrypted JSONL audit
├── pipeline.py      # Public API: build_pipeline(), process_document()
└── config.py        # env-driven Pydantic settings

api/main.py          # FastAPI HTTP service
app.py               # Gradio Space entry point
tests/               # Pytest suite, mock backend
docker/              # Dockerfile + compose stack with llama-server
```

## Source

Wiest IC, Leßmann ME, Wolf F, et al. *Deidentifying Medical Documents with Local, Privacy-Preserving Large Language Models: The LLM-Anonymizer.* NEJM AI 2024. DOI: [10.1056/AIdbp2400537](https://ai.nejm.org/doi/full/10.1056/AIdbp2400537)

## License

MIT

## Local project consolidation

This project is now consolidated under `C:\Users\j_car\KnowledgeGraph\tools\pii-redactor`.

Related reference material is kept in `docs/references/`, including the NEJM AI LLM-Anonymizer paper used to ground the de-identification design.
