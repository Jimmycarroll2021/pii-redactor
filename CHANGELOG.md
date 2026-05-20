# Changelog

## [0.4.3] — 2026-05-20

### Added — rules-only extension (Path B, half-day patch)

Phase 6.2 multi-adapter LoRA work was halted at the frozen-bench HOLD-CHECK
(Medical narrative could not be recovered from public replay datasets).
v0.4.3 ships the parallel "Phase 5.1" rule-layer extension that closes
the rest of the Phase 4 sector gap without retraining: extra org-suffix
vocabulary, extra informal-location regexes, and the
`private_address` → address-vs-location schema disambiguation called out
by the Phase 6.2 Codex peer review.

- **`au_org_loc._ORG_SUFFIX_PATTERN`** extended with medical, legal, and
  community suffixes: `Clinic`, `Medical Centre`, `Health Service`,
  `Practice`, `Lawyers`, `Legal`, `Solicitors`, `Barristers`, `Chambers`,
  `Cooperative`, `Mutual`, `Society`, `Association`, `Foundation`,
  `Trust`. The capitalised-token run now also allows `&`-separated
  partners so `Smith & Brown Lawyers` matches as a single span.
- **`au_org_loc._ORG_LEGAL_PARTNERS_PATTERN`** (new) — catches
  "Smith & Partners", "Jones and Associates Solicitors" compound names.
- **`au_org_loc._ORG_MEDICAL_FACILITY_PATTERN`** (new) — non-suffix
  medical-facility names: `Bayside Medical Centre`, `Northside GP Clinic`,
  `Aged Care`, `Healthcare`, `Day Hospital`, `Day Surgery`,
  `Specialist Centre`.
- **`au_org_loc._INFORMAL_REGION_PATTERN`** (new) — high-precision
  Greater/Inner/Outer/Northern/Southern/Eastern/Western informal regions
  anchored on a known city or compass direction.
- **`au_org_loc._NAMED_REGION_PATTERN`** (new) — well-known AU regions
  with optional `the ` prefix: `Top End`, `Outback`, `Pilbara`,
  `Goldfields`, `Hunter Valley`, `Yarra Valley`, `Barossa Valley`,
  `Margaret River`, `McLaren Vale`, `Mornington Peninsula`, `Sunshine
  Coast`, `Gold Coast`, `Central Coast`, `Blue Mountains`,
  `Snowy Mountains`, `Great Dividing Range`, `Daintree`, `Kakadu`,
  `Red Centre`, `Atherton Tableland`.
- **`au_org_loc._CBD_PATTERN`** (new) — `Sydney CBD`, `CBD of Melbourne`,
  `Brisbane Central Business District` style references.

### Added — `private_address` → address/location disambiguator

The Phase 6.2 Codex peer review identified the root cause of the
`location` recall floor: `openai/privacy-filter` collapses BOTH postal
addresses AND standalone locations into a single `private_address`
label, so the per-category metric for `location` was stuck at ~0% even
when the model recovered the spans. v0.4.3 fixes this at the
rule layer instead of via retraining.

- **`au_resolver._disambiguate_address_vs_location`** (new) — span-local
  structural heuristic. Returns `"address"` when the span has a street
  number + street suffix, a 4-digit postcode, a street suffix alone, or
  a PO/GPO Box / Locked Bag prefix; returns `"location"` for pure
  suburb / region / state references.
- **`au_resolver.resolve_account_numbers`** wires the disambiguator into
  every `private_address` candidate before the PIICategory mapping, so
  the production pipeline emits `LOCATION` for `Greater Sydney`,
  `Inner West`, `the Yarra Valley`, `NSW`, `Northern Territory`, etc.,
  while keeping `23 Collins Street, Melbourne VIC 3000`,
  `1/45 Park Road, Brunswick`, and `PO Box 123, Sydney NSW 2000` as
  `ADDRESS`.

### Added — gazetteer expansion (~90 new entries)

`pii_redactor/data/gazetteers/au_organisations.txt` grew from ~300 to
~390 entries. New sections:

- **Top-tier AU law firms (not previously covered)** — Arnold Bloch
  Leibler, Bartier Perry, Carter Newell Lawyers, Clayton Utz (existing),
  Clamenz Lawyers, Clifford Chance Australia, Colin Biggers & Paisley,
  Cornwalls, DLA Piper Australia, DibbsBarker, Dentons Australia,
  Gadens, Henry William Lawyers, Hicksons, Hogan Lovells Australia,
  HopgoodGanim Lawyers, Jackson McDonald, K&L Gates Australia, Kennedys
  Australia, Lavan, Lipman Karas, Macpherson Kelley, McCabe Curwood,
  McInnes Wilson Lawyers, Meridian Lawyers, Moray & Agnew, Norton
  Gledhill, Norton White, Pinsent Masons Australia, Sparke Helmore,
  Squire Patton Boggs Australia, TressCox Lawyers, Wotton + Kearney
  (~33 firms).
- **AU medical / aged-care / hospital groups** — ICON Group, ICON
  Cancer Centre, Heritage Care, Estia Health, Regis Aged Care, Bolton
  Clarke, BlueCross Aged Care, Opal HealthCare, Allity Aged Care,
  Arcare Aged Care, Aurora Healthcare, Healthe Care, GenesisCare,
  Montserrat Day Hospitals, Nexus Hospitals, Macquarie Health
  Corporation, Adventist HealthCare, St John of God Health Care,
  UnitingCare Queensland, Silver Chain Group, Royal Flying Doctor
  Service, HammondCare, Anglicare, Mission Australia, Wesley Mission
  (~25 groups).
- **AU MedTech / health tech** — Pro Medicus, Audinate, Nuix,
  Nanosonics, PolyNovo, Medical Developments International, Mesoblast,
  Paradigm Biopharmaceuticals, Avita Medical, Telix Pharmaceuticals,
  Imugene, Volpara Health Technologies, Atomo Diagnostics, Compumedics,
  ResApp Health, Universal Biosensors, EMVision Medical Devices,
  Micro-X, Next Science, Aroa Biosurgery, Race Oncology, Neuren
  Pharmaceuticals, Clinuvel Pharmaceuticals, Starpharma, Patrys
  (~25 companies).
- **Additional federal regulators** — Aged Care Quality and Safety
  Commission, Fair Work Ombudsman, Fair Work Commission, Australian
  Skills Quality Authority, Tertiary Education Quality and Standards
  Agency, Office of the eSafety Commissioner, Office of the National
  Data Commissioner, National Health and Medical Research Council
  (NHMRC), Cancer Australia, Department of Health.

### Added — tests (148 total, +11 new)

- `test_clinic_suffix_match` — Medical Centre suffix tags as ORGANISATION
- `test_legal_firm_suffix_match` — `Lawyers`, `& Partners` suffixes match
- `test_informal_location_greater_sydney`
- `test_informal_location_inner_west`
- `test_informal_location_regional` — `the Yarra Valley`, `Pilbara`
- `test_address_vs_location_disambiguation_full_address` — street + suburb → address
- `test_address_vs_location_disambiguation_standalone_suburb` — pure
  suburb / region / state → location
- `test_address_vs_location_disambiguation_with_postcode_no_street` —
  postcode-bound suburb stays as ADDRESS
- `test_address_vs_location_disambiguation_po_box` — PO Box / GPO Box /
  Locked Bag stay as ADDRESS
- `test_address_vs_location_disambiguation_adversarial` —
  "Smith lives in Sydney" → LOCATION; "77 Smith Street, Wollongong" → ADDRESS
- `test_au_resolver_post_processes_private_address_label` — end-to-end
  resolver re-tagging via `resolve_account_numbers`

All 148 tests pass (137 from v0.4.2 + 11 new).

### Compatibility

- v0.4.2 default config unchanged. Same env knobs, same backend defaults.
- The `private_address` disambiguator is on by default — there is no
  regression on existing ADDRESS spans (all 137 v0.4.2 tests pass) but
  any client that relied on the model emitting only `address` for
  standalone-location spans will now see `LOCATION` for those spans.
- HF Hub adapter UNCHANGED (still `v0.4.0` weights at
  `JimmyBhoy/redact-au-1b`).
- Wheel deps unchanged; no new transitive dependencies.
- Container image `redact-au-hybrid:0.4.3` is a drop-in replacement for
  `:0.4.2` with the same env knobs.

### Frozen bench HOLD-CHECK

Gretel-100 + Medical-50 frozen-bench must HOLD exactly the v0.4.2 numbers
(Gretel 93.67% / 2 leaks, Medical 99.71% / 0 leaks) — automated revert
on failure per the v0.4.3 patch contract. The rules-only design choice
explicitly avoids any change that could lift Medical / drop Gretel — the
disambiguator only re-categorises spans that the model already emitted.

## [0.4.2] — 2026-05-20

### Changed — README + PyPI description refresh (no functional changes)
- README "Why this design" section reframed around the two-tier
  (LoRA default / Llama opt-in) v0.4.x architecture instead of the
  v0.1.x single-Llama story.
- "Measured performance" section replaced with v0.4.1 frozen-bench
  numbers (Tier 1 LoRA / Tier 2 +llama / legacy CPU baseline columns)
  plus the multi-sector head-to-head vs Microsoft Presidio.
- "Detected categories" table extended with `organisation` and
  `location` (introduced in v0.4.1).
- "Configuration" env-var table updated with the v0.4.x knobs
  (`PIIR_LORA_ADAPTER`, `PIIR_LLAMA_BACKEND`, `PIIR_LLAMA_GATE`,
  `PIIR_VLLM_URL`, `PIIR_REGEX_ORGANISATION`, `PIIR_REGEX_LOCATION`)
  and the new defaults (`PIIR_BACKEND=transformers_au_finetuned`,
  `PIIR_LLAMA_BACKEND=disabled`).
- "Testing" badge bumped from 58 → 137.
- "Architecture" file-tree extended with `hybrid/` subpackage +
  `data/gazetteers/`.

No code, model, or schema changes. The v0.4.1 wheel that's currently
on PyPI shipped with a stale README baked into the metadata; this
release exists solely to refresh what PyPI displays. Functional
behaviour is byte-identical to v0.4.1.

## [0.4.1] — 2026-05-20

### Added — AU organisation + location recognisers (Phase 5)
- New `pii_redactor.hybrid.au_org_loc` module — gazetteer + regex
  recognisers for the two highest-impact gaps identified in the Phase 4
  sector bench (`organisation` recall 3-29%, `location` recall 3-77%).
- `AUOrganisationRecogniser`: exact gazetteer match for ~300 curated AU
  federal + state agencies, hospitals, universities, banks, top law firms;
  corporate-suffix pattern (`Pty Ltd / Limited / LLP / Corp / Group / …`);
  Department/Ministry/Authority pattern; hospital + university patterns;
  context-gated acronym detection (~80 mappings — acronyms only tag when
  expansion is nearby).
- `AULocationRecogniser`: state abbreviations (NSW/VIC/…), full state
  names, postcode-in-context (4-digit number near a suburb/state),
  16,165-entry CC0 suburb gazetteer with disambiguation guard for
  ambiguous names ("Hill", "Beach"), region patterns ("Greater Sydney",
  "Inner West").
- Two new `PIICategory` values: `ORGANISATION` ("organisation") and
  `LOCATION` ("location"). Pipeline `_merge_with_au_priority` places
  them just below `ADDRESS` so the address recogniser still wins on
  overlaps.
- Bundled gazetteer files under `pii_redactor/data/gazetteers/` —
  packaged via `[tool.setuptools.package-data]` and `MANIFEST.in`.

### Added — env knobs
- `PIIR_REGEX_ORGANISATION=true|false` (default `true`) — toggle org recogniser.
- `PIIR_REGEX_LOCATION=true|false` (default `true`) — toggle location recogniser.
- `PIIR_ORG_GAZETTEER_PATH=...` / `PIIR_LOC_GAZETTEER_PATH=...` — path
  overrides for custom gazetteers.

### Added — tests (137 total, +11 new)
- `test_organisation_recogniser_loads_gazetteer`
- `test_organisation_pty_ltd_match`
- `test_organisation_gov_agency_match`
- `test_organisation_hospital_match`
- `test_organisation_acronym_requires_context`
- `test_location_state_abbrev_match`
- `test_location_postcode_context_match`
- `test_location_suburb_gazetteer_match`
- `test_organisation_disabled_via_env`
- `test_location_disabled_via_env`
- `test_org_loc_no_double_tag_with_address` — regression guard for
  existing `au_address` recall

### Measured (RTX 4090, v0.4.1 vs v0.4.0 sector bench)

Per-sector aggregate sensitivity (lenient), Tier 1:

| Sector | v0.4.0 | v0.4.1 | Δ |
|---|---:|---:|---:|
| federal-gov-official    | 88.17% | 93.15% | +4.98 pp |
| state-health-hospitals  | 92.91% | 93.55% | +0.64 pp |
| legal-small-mid         | 78.99% | 85.75% | +6.76 pp |
| medtech-health-ai       | 87.52% | 91.57% | +4.05 pp |

Per-AU-category organisation recall lifts:

| Sector | v0.4.0 | v0.4.1 | Δ |
|---|---:|---:|---:|
| federal    | 3.1% (4/131)    | 58.78% (77/131) | +55.68 pp |
| state-health | 26.9% (29/108) | 39.81% (43/108) | +12.91 pp |
| legal | 28.8% (96/333)        | 51.65% (172/333) | +22.85 pp |
| medtech | 6.5% (10/154)        | 52.60% (81/154) | +46.10 pp |

federal location recall: 3.3% → 36.67% (+33.37 pp).

### Frozen bench HOLD (Gretel-100 + Medical-50)
- Gretel-100 sensitivity: **93.67%** (matches v0.4.0 exactly)
- Gretel leaks: **2** (matches v0.4.0)
- Medical-50 sensitivity: **99.71%** (matches v0.4.0)
- Medical leaks: **0** (matches v0.4.0)

No retraining; no model changes. Pure rule + gazetteer augmentation.
The frozen bench held perfectly because the org/loc recognisers don't
overlap with the existing `address`/`name`/`email` span types.

### Not yet at 97% gate
Phase 5 closed roughly two thirds of the gap to the 97% sector publish
gate. Residual misses are dominated by long-tail org names (small/mid
law firms, mid-tier clinics) and informal location phrases ("the Top
End", "the western suburbs"). See `benchmarks/sector-scorecard-v0.4.1.md`
for the full breakdown and recommended Phase 5.1 / Phase 6 follow-ups.

### Compatibility
- v0.4.0 default config (LoRA finetuned base, llama disabled) unchanged.
- Wheel deps unchanged; no new transitive dependencies.
- Container image `redact-au-hybrid:0.4.1` is a drop-in replacement
  for `:0.4.0` with the same env knobs + new optional org/loc toggles.

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
intended for evaluation and deployment inside systems handling:

- Australian government documents (OFFICIAL / OFFICIAL: Sensitive tier)
- Clinical narratives (AU + general)
- Regulatory identifier extraction with checksum validation
  (TFN mod-11, ABN mod-89, Medicare, IHI, ACN)
- Pipelines supporting APP 11 / 11.2 / 12 workflows where validated by
  the deploying organisation

This release is **not** a PSPF, IRAP, clinical-safety, or legal
compliance certification. Redaction output is not legal advice and not
a guarantee of de-identification. Deployment is subject to the entity's
PSPF, APP, security architecture, access-control, audit, retention, and
risk-acceptance processes. Before production use on a new agency,
hospital, research, or customer corpus, run a local acceptance benchmark
on representative documents — published numbers are not a substitute
for site-specific validation.

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
