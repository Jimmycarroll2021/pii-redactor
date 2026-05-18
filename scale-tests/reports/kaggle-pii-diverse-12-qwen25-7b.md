# Kaggle PII Data Test - qwen2.5:7b

**Generated:** 2026-05-03
**Source:** Kaggle PII Detection competition training data mirror
**Mirror used:** https://huggingface.co/datasets/metaboulie/Tidied-PII-Detection-Kaggle-7k
**Raw file:** scale-tests/external/kaggle-pii-detection-7k/train.json
**Converted fixture:** scale-tests/fixtures/kaggle-pii-7k-converted
**Diverse qwen fixture:** scale-tests/fixtures/kaggle-pii-diverse-12
**Run:** scale-tests/runs/20260503-kaggle-pii-diverse-12-qwen25-7b
**Backend:** Ollama
**Model:** qwen2.5:7b

## Verdict

Fail for Kaggle-style PII coverage.

The pipeline processed the Kaggle-derived 12-document diverse subset, but expected PII values remained in the safe output payload.

## Results

| Metric | Value |
|---|---:|
| Documents processed | 12 |
| Status | OK |
| Checked PII leaks | 11 |
| Mean latency ms | 16701.32 |
| Docs/sec | 0.0599 |

## Expected vs Detected

| PII type | Expected labels | Detected |
|---|---:|---:|
| address | 2 | 1 |
| email | 7 | 8 |
| name | 14 | 5 |
| patient_id / username / id | 4 | 0 |
| phone | 5 | 5 |
| url | 5 | 4 |

## Leak Breakdown

| Category | Leaks |
|---|---:|
| name | 9 |
| patient_id | 1 |
| url | 1 |

## Interpretation

The Australian synthetic/contextual PII proof passes, but Kaggle student-writing data exposes a different failure mode: names embedded in essays and Kaggle-specific ID/username/URL patterns are not fully captured by the current prompt/category setup.

This is useful test data. It should be used as a new regression target before claiming broad PII coverage.

## Files Created

- Converter: scale-tests/convert_kaggle_pii.py
- Raw Kaggle-derived mirror: scale-tests/external/kaggle-pii-detection-7k/train.json
- Converted full PII fixture: scale-tests/fixtures/kaggle-pii-7k-converted
- Diverse qwen subset: scale-tests/fixtures/kaggle-pii-diverse-12
- Run summary: scale-tests/runs/20260503-kaggle-pii-diverse-12-qwen25-7b/summary.json
- Run results: scale-tests/runs/20260503-kaggle-pii-diverse-12-qwen25-7b/results.jsonl

## Next Fix Target

Improve detection for:

1. Student names embedded in essay text.
2. Kaggle ID_NUM and USERNAME patterns mapped to generic IDs.
3. Personal URLs, including malformed/truncated URL labels from the Kaggle token data.
