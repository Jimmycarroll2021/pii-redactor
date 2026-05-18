# Proper PII Test Setup

**Generated:** 2026-05-03
**Status:** Implemented
**Latest proper run:** scale-tests/runs/20260503-pii-eval-proper-pass
**Latest proper result:** PASS

## What Was Added

- Consolidated eval runner: scale-tests/run_pii_eval_suite.py
- Fixture registry generator: scale-tests/generate_fixture_registry.py
- Fixture registry: scale-tests/fixtures/registry.json
- User-supplied ZIP converter: scale-tests/convert_user_supplied_pii.py
- Updated external dataset converters for username and generic ID categories.
- Detector support for username and generic_id categories.
- Expanded regex prepass for usernames, generic IDs, SSNs, international phones, URLs, and date/time formats.

## User-Supplied Data Converted

| Source ZIP | Fixture |
|---|---|
| scale-tests/external/user-supplied/archive.zip | scale-tests/fixtures/user-pii-dataset-csv-1000 |
| scale-tests/external/user-supplied/archive (1).zip | scale-tests/fixtures/user-openpii-validation-en-1000 |

pii_dataset.csv.zip is a duplicate of rchive.zip and remains staged in external data.

## Registered Fixtures

The registry currently contains 11 proper-test fixtures/runs, covering:

- Project AU synthetic corpora
- qwen proof fixtures
- hidden 40-page proof fixture
- Kaggle-derived PII data
- AI4Privacy/OpenPII data
- Gretel PII masking data
- User-supplied CSV ZIP data
- User-supplied OpenPII ZIP data

## Latest Proper Test Result

| Metric | Value |
|---|---:|
| Failed fixtures | 0 |
| Total fixture runs | 11 |
| Required leak threshold | 0 |

## Commands

Run the full deterministic proper suite:

`powershell
py -3.12 scale-tests\run_pii_eval_suite.py --profile proper --backend mock
`

Run the quick deterministic suite:

`powershell
py -3.12 scale-tests\run_pii_eval_suite.py --profile quick --backend mock
`

Run bounded qwen samples explicitly:

`powershell
$env:PIIR_OLLAMA_MODEL='qwen2.5:7b'
$env:PIIR_OLLAMA_URL='http://127.0.0.1:11434'
py -3.12 scale-tests\run_pii_eval_suite.py --profile quick --backend ollama --qwen-sample-limit 1
`

## Notes

The deterministic proper suite is the default gate because it can run across thousands of documents quickly. qwen testing is explicit because the local model is much slower, especially for the 40-page hidden-middle proof.
