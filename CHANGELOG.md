# Changelog

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
