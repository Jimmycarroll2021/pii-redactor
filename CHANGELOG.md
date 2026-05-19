# Changelog

## [0.2.0] — 2026-05-19

### Added — hybrid transformers + AU validator backend
- New `pii_redactor.hybrid` module — orchestrates `openai/privacy-filter` (Apache 2.0 token classification, ~50M active params, ~110 ms/doc on RTX 4090) as a fast first-pass NER, then routes generic `account_number` / `secret` spans through the existing AU validators (TFN, ABN, ACN, Medicare, BSB checksums) + a structural matcher (IHI, MRN, Passport, DL, CRN) + label-context priors to assign precise AU categories. Drop-in replacement for the LLM-backed `PIIDetector`.
- `PIIR_BACKEND=transformers_au` env-selectable backend (existing `mock` / `ollama` / `llama_cpp` / `hf` paths unchanged).
- `pii_redactor.hybrid.openai_backend.OpenAIPrivacyFilter` — thin wrapper around the HF transformers pipeline with lazy GPU load, warmup, and char-offset span normalisation.
- `pii_redactor.hybrid.au_resolver` — converts OpenAI's generic categories into AU-specific labels using checksum-then-structural-then-label-prior resolution.
- `pii_redactor.hybrid.regex_supplement` — runs the existing regex_first_pass over text to catch usernames + AU phone/address fragments OpenAI misses, with category-override rules where regex is more specific (e.g. username vs name).
- `pii_redactor.hybrid.pipeline.HybridDetector` + `build_hybrid_pipeline()` — wire the hybrid detector into the existing `Pipeline` (audit + redactor unchanged).
- New optional dependency group: `pip install "pii-redactor-au[hybrid]"` (pulls `torch>=2.1`, `transformers>=4.40`).
- 20 new unit tests under `tests/test_hybrid.py` (78 total passing).

### Added — RTX 4090 FastAPI deployment
- `redact-au-hybrid` Docker image — CUDA 12.8 + Python 3.12 + torch 2.12 + transformers 5.x, runs the `/redact`, `/redact/batch`, `/reidentify`, `/health`, `/info`, `/metrics` endpoints with the hybrid backend GPU-warm at startup.
- `/health` returns `{"status":"ok","backend":"transformers_au","gpu":"RTX 4090"}` when the hybrid backend is active.
- Deployed at `/mnt/ai/services/redact-au-hybrid/` on the RTX 4090, accessible at `http://rtx-ts:8000`.

### Measured (RTX 4090 / Gretel-100 + Medical-50)
- Throughput: **8.97 docs/sec Gretel, 7.01 docs/sec Medical** — at parity with raw `openai/privacy-filter` (validator overhead is microseconds). **140-143× the v0.1.2 CPU baseline** (0.064 / 0.049 docs/sec).
- Sensitivity: **91.6% Gretel, 90.1% Medical** (vs 99.6% / 100% on v0.1.2 baseline). Below the 99.4% target — see `benchmarks/hybrid-vs-baseline.md` for the per-category breakdown and the actionable closing path.
- Zero leaks on Medical-50; 7 leaks on Gretel-100 (down from baseline's 1; concentrated in `generic_id` and AU phones that OpenAI fragments).

### Compatibility
- v0.1.2 backends (`mock` / `ollama` / `llama_cpp` / `hf`) untouched. All 58 existing tests still pass.

## [0.1.2] — 2026-05-18

### Distribution name change
- PyPI distribution renamed from `pii-redactor` to **`pii-redactor-au`** (the unqualified name is owned by another project on PyPI)
- Import name remains `pii_redactor` — no consumer code change
- Install: `pip install pii-redactor-au`
- Live at: https://pypi.org/project/pii-redactor-au/0.1.2/

### Added
- Synthetic medical PII fixture (50 docs, 345 labels, 15 AU-identifier docs) — `scale-tests/fixtures/synthetic-medical-50/`
- Deterministic fixture generator — `scale-tests/generate_synthetic_medical.py`
- `.planning/PASS-GATE.md` — verifiable Wiest sensitivity record

### Changed
- Address-extraction prompt — strengthened with explicit suburb/postcode/state cues and "over-extraction acceptable" directive
- DoB-extraction prompt — tightened for "DOB on file" / JSON-embedded contexts
- 2 new few-shot examples covering compound addresses and bare-suburb cases
- README "Measured performance" subsection with run-dir references
- FastAPI `version` and `/info` now derive from `pii_redactor.__version__` (single source of truth)

### Fixed
- Phone regex no longer false-matches 11-digit ABN spacing (`12 345 678 901`)
- Phone regex now uses explicit alternations per format (AU/UK/US/dotted/dashed) with `(?<!\d)…(?!\d)` boundary guards
- 2 previously failing unit tests now pass (`test_abn_string_does_not_produce_phone_span`, `TestPhoneRegex::test_no_match_inside_abn`)

### Performance
- Gretel-100 sensitivity: **99.58%** (up from 97.89%) using Llama-3.1-8B-Instruct via Ollama
- Synthetic-medical-50 sensitivity: **100.00%** across 345 labels
- 58/58 unit tests passing (up from 56/58)
- Mock-baseline regression: 0 leaks, 1917 docs/sec (no regression)

## [0.1.1] — 2026-05-04

### Initial baseline
- 3 bug-fixes (phone format, BSB false positives, phone-in-ABN — last regressed; see 0.1.2)
- 12-fixture eval harness
- Production gate PASS (compileall, deterministic_registry, encrypted_audit, ollama_quick)
