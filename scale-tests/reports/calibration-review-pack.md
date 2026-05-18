# Calibration Review Pack

**Generated:** 2026-05-03
**Phase:** 11 - Calibration Review Pack

## Verdict

Pass for review tooling and initial sample generation.

## Outputs

- Exporter: scale-tests/export_review_pack.py
- Sample pack: scale-tests/review-packs/20260503-mock-5docs
- Human review file: scale-tests/review-packs/20260503-mock-5docs/REVIEW.md
- Machine-readable samples: scale-tests/review-packs/20260503-mock-5docs/samples.jsonl

## How To Use

Generate a fast deterministic review pack:

`powershell
py -3.12 scale-tests\export_review_pack.py --documents scale-tests\fixtures\synthetic-1000-seed42\documents.jsonl --expected scale-tests\fixtures\synthetic-1000-seed42\expected_labels.jsonl --backend mock --limit 20 --out scale-tests\review-packs\<pack-name>
`

Generate a smaller qwen-backed review pack:

`powershell
$env:PIIR_OLLAMA_MODEL='qwen2.5:7b'
$env:PIIR_OLLAMA_URL='http://127.0.0.1:11434'
py -3.12 scale-tests\export_review_pack.py --documents scale-tests\fixtures\synthetic-1000-seed42\documents.jsonl --expected scale-tests\fixtures\synthetic-1000-seed42\expected_labels.jsonl --backend ollama --limit 3 --out scale-tests\review-packs\<pack-name>
`

## Status

The tooling exists. Human review itself is still a production-readiness task and must be completed by a reviewer before real sensitive documents are processed.
