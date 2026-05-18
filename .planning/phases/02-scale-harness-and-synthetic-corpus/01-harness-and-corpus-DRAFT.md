# Phase 2 Draft Plan: Scale Harness and Synthetic Corpus

## Objective

Create repeatable corpus generation plus direct-library and HTTP batch benchmark runners.

## Candidate Files

- `scale-tests/generate_corpus.py`
- `scale-tests/run_library_benchmark.py`
- `scale-tests/run_http_batch_benchmark.py`

## Acceptance Criteria

- Corpus generator uses deterministic seed.
- Expected PII labels are separate from source documents.
- Direct and HTTP runners output JSONL results plus summary JSON.
- Parameters include document count, concurrency, seed, backend, and output path.
