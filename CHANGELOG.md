# Changelog

## [0.4.0] — 2026-05-19

### BREAKING — default llama backend disabled
- `PIIR_LLAMA_BACKEND` default changed from `auto` → `disabled`. The Llama
  narrative-pass is no longer in the default hot path. Users wanting the
  prior v0.3.x behaviour should set `PIIR_LLAMA_BACKEND=vllm` or `=ollama`
  explicitly.
- Equivalent: `PIIR_LLAMA_ENABLED=false` still disables the pass entirely.

### Added — LoRA-finetuned `openai/privacy-filter` (`redact-au-1b`)
- `pii_redactor.hybrid.finetuned_backend.FinetunedOpenAIBackend` — loads
  base `openai/privacy-filter` (Apache 2.0) + a LoRA adapter via PEFT and
  merges them for zero-overhead inference. Drop-in subclass of
  `OpenAIPrivacyFilter` — same span schema, same `predict_with_scores()`.
- New env knob `PIIR_LORA_ADAPTER` — path to LoRA adapter directory.
  Default: `/mnt/ai/adapters/redact-au-1b/best` (the autonomous loop's
  top-1 adapter on RTX 4090).
- New backend value `PIIR_BACKEND=transformers_au_finetuned`.
- Fallback chain: `transformers_au_finetuned → transformers_au → ollama`
  (`PIIR_LLAMA_BACKEND` controls the last hop; default = disabled).
- HF Hub model card published at `JimmyBhoy/redact-au-1b` (Apache 2.0).

### Added — config + library
- `Config.lora_adapter_path` (read from `PIIR_LORA_ADAPTER`).
- `peft>=0.13.0` added to `[hybrid]` and `[all]` optional dependency
  groups.
- 6 new tests covering FinetunedOpenAIBackend, the disabled short-circuit,
  fallback chain, and the new config knob (126 tests total).

### Performance (RTX 4090, v0.4.0, llama=disabled default)
- Held-out sensitivity: **97.41%** overall, **100.00%** AU-synthetic,
  **99.57%** medical-aug, **92.00%** Gretel held-out.
- Composite score (sensitivity − 0.001·leaks − forgetting-penalty): **0.927**.
- General-PII regression (ai4privacy held-out, vs baseline 0.672):
  **0.882** — no forgetting penalty.
- Container `redact-au-hybrid:0.4.0` healthy on rtx-ts:8000 reporting
  `backend=transformers_au_finetuned`, `adapter=redact-au-1b`.
- Frozen-bench measurements added in `benchmarks/v0.4-vs-baseline.md`.

### Product tiers

v0.4.0 ships as a **two-tier product**:

**Tier 1 — AU government + clinical (default)**
- Backend: `transformers_au_finetuned`, llama disabled
- Throughput: 6.37 d/s (Gretel-100) / 5.05 d/s (Medical-50) on RTX 4090
- Sensitivity: 99.71% on Medical-50 with 0 leaks; 93.67% on Gretel-100
  with 2 leaks (both non-AU social-handle usernames)
- Suitable for: AU OFFICIAL / OFFICIAL: Sensitive workloads in gov +
  healthcare + clinical research
- Tested workloads: AU clinical narratives, AU regulatory identifiers
  (TFN/ABN/Medicare/IHI/MRN/BSB/CRN), general PII

**Tier 2 — General + social (opt-in)**
- Backend: `transformers_au_finetuned` + llama vLLM second pass
- Activate: `PIIR_LLAMA_BACKEND=vllm`
- Throughput: 1.39 d/s (Gretel-100) / 1.08 d/s (Medical-50)
- Sensitivity: 97.89% on Gretel-100, 100% on Medical-50, 0 leaks both
- Suitable for: workloads with international phone formats, social
  handles, foreign locality names, label-less ID strings

### Claim scope

v0.4.0 is **NOT** a generalist global-PII redaction system. It is
optimised for:

- Australian government documents (OFFICIAL / OFFICIAL: Sensitive tier)
- Clinical narratives (AU + general)
- Regulatory identifier extraction with checksum validation
  (TFN mod-11, ABN mod-89, Medicare, IHI, ACN)
- AU privacy law compliance (Privacy Act 1988, APP 11/11.2/12)

For US/EU/UK PII at production-grade recall, use Tier 2 or evaluate
Microsoft Presidio / AWS Comprehend Medical / Azure Cognitive Services
PII Detection as alternatives.

### Known limitations

- 6 of 237 Gretel-100 FNs in Tier 1 are non-AU edge formats
  (international phone+extension, social handles, single-word foreign
  localities, label-less IDs). Tier 2 closes these. See
  `benchmarks/v0.4-leak-taxonomy.md` for full taxonomy.
- General PII regression eval on ai4privacy held-out: 91.05%
  (vs untuned base 67.22%). Recall holds on US/UK style PII at
  OFFICIAL-tier quality but not Wiest-equivalent.
- Bench fixtures are small (Gretel-100, Medical-50). Confidence
  intervals on the 99.71% Medical claim are wide (1 missed entity in
  345 annotations).
- Synthetic-vs-real generalisation gap is unmeasured. Training corpus is
  ~95% synthetic (AU privacy + ethics constraints).
- PROTECTED / SECRET / TOP SECRET / Cabinet classification is out of
  scope; requires IRAP assessment (not yet held).

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
