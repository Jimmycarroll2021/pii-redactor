# Kaggle PII Pull and Test

**Generated:** 2026-05-03
**Official competition:** pii-detection-removal-from-educational-data
**Official Kaggle download status:** blocked by Kaggle account competition access (403 Forbidden, userHasEntered=False)
**Usable source:** public Kaggle-derived Hugging Face mirror
**Mirror:** metaboulie/Tidied-PII-Detection-Kaggle-7k

## Verdict

Fail for Kaggle-style PII coverage.

We could not download the official competition files yet because the Kaggle account has not accepted/entered the competition rules. We did download and test a public Kaggle-derived mirror. That test exposed real coverage gaps.

## Data Pulled

| Item | Path |
|---|---|
| Raw mirror JSON | scale-tests/external/kaggle-pii-detection-7k/train.json |
| Converter | scale-tests/convert_kaggle_pii.py |
| Converted fixture | scale-tests/fixtures/kaggle-pii-7k-converted |
| Diverse qwen subset | scale-tests/fixtures/kaggle-pii-diverse-12 |

## Broad Converted Mirror Smoke

| Metric | Value |
|---|---:|
| Documents | 945 |
| Backend | mock deterministic |
| Checked leaks | 76 |
| patient_id leaks | 69 |
| phone leaks | 6 |
| url leaks | 1 |

Run: scale-tests/runs/20260503-kaggle-pii-7k-converted-mock-945docs

## qwen Diverse Subset Test

| Metric | Value |
|---|---:|
| Documents | 12 |
| Backend | qwen2.5:7b via Ollama |
| Checked leaks | 11 |
| name leaks | 9 |
| patient_id leaks | 1 |
| url leaks | 1 |

Run: scale-tests/runs/20260503-kaggle-pii-diverse-12-qwen25-7b

## Interpretation

The current system works on our Australian structured/contextual proof packs, but Kaggle student-writing PII is a different distribution. It exposes gaps around:

1. Student names embedded naturally in essays.
2. Kaggle ID_NUM and username-style identifiers.
3. Non-Australian phone number formats.
4. Personal URLs, including malformed/truncated labels.

## Next Engineering Target

Treat this as a new benchmark family. Fix Kaggle-style coverage before making broad PII claims beyond the Australian structured/contextual cases.

## Official Kaggle Access Step

To pull the official competition files directly, the Kaggle account must accept the competition rules in the browser. Current CLI auth is valid, but download remains blocked by Kaggle access state.
