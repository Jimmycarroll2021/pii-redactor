# Full all-data PII deterministic evaluation

- Generated: 2026-05-03T07:57:20.240066+00:00
- Run directory: `scale-tests\runs\20260503-pii-eval-full-all-data-final6`
- Registry: `scale-tests/fixtures/registry-full.json`
- Backend: `mock` deterministic regex/mock pipeline
- Fixture groups: 11
- Documents processed: 48382
- Leak total: 0
- Status: PASS

## Fixture results

| Fixture | Documents | Leaks | Status |
|---|---:|---:|---|
| `ai4privacy-openpii-english-all` | 3923 | 0 | PASS |
| `gretel-pii-masking-en-all` | 4066 | 0 | PASS |
| `kaggle-pii-7k-converted` | 6807 | 0 | PASS |
| `kaggle-pii-diverse-12` | 12 | 0 | PASS |
| `pii-context-proof-20260503` | 6 | 0 | PASS |
| `pii-hidden-middle-40page-20260503` | 1 | 0 | PASS |
| `pii-proof-20260503` | 2 | 0 | PASS |
| `synthetic-1000-seed42` | 1000 | 0 | PASS |
| `synthetic-2000-seed43` | 2000 | 0 | PASS |
| `user-openpii-validation-en-all` | 26131 | 0 | PASS |
| `user-pii-dataset-csv-all` | 4434 | 0 | PASS |

## Scope notes

- This run used the full prepared local fixture registry, including full user CSV, English OpenPII validation data, Gretel test data, AI4Privacy English data, Kaggle-converted data, synthetic scale corpora, and proof fixtures.
- Mock backend leak scoring excludes name, address, and date_of_birth because those require LLM extraction; structured fields are leak-scored.
- `processed_at` metadata is excluded from leak comparison so benchmark wall-clock times do not create false positives for time labels.
- The large OpenPII train JSONL inside the user ZIP was not included in this registry; the English validation split was included in full.
