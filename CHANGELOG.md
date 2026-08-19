# Changelog

## [0.4.5] — 2026-06-30

### Fixed

- **Engine HTTP startup crash (RUN-01):** `api/main.py` referenced an undefined `_auth_disabled_ok()` function, causing the FastAPI app to crash at startup whenever `PIIR_API_KEY` was unset. Replaced with `http_auth.auth_disabled_ok()`.
- **Version drift:** `pii_redactor.__version__` now matches `pyproject.toml` (`0.4.5`). README badge and headline updated to reflect the current test count.

### Added

- FastAPI smoke tests in `tests/test_api_main_smoke.py`: verify `/health`, `/info`, and fail-closed `/redact` behavior with and without an API key.
- `httpx` added to dev dependencies for FastAPI `TestClient` support.

### Changed

- Migrated `api/main.py` from deprecated `@app.on_event("startup")` to a modern
  `lifespan` context manager, removing FastAPI deprecation warnings in tests.
- `.env.example` backend comment now lists all supported backends including the hybrid substrates.

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
