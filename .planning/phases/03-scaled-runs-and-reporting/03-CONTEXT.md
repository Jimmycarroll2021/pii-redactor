# Phase 3 Context: Scaled Runs and Reporting

## Phase Goal

Run the scale harness from Phase 2 and produce durable correctness, safety, and performance reports.

## Requirements Covered

- SAFE-01 through SAFE-05
- PERF-01 through PERF-04
- DOCS-01 through DOCS-03

## Inputs Expected from Phase 2

- `scale-tests/generate_corpus.py`
- `scale-tests/run_library_benchmark.py`
- `scale-tests/run_http_batch_benchmark.py`
- `scale-tests/fixtures/`
- `scale-tests/runs/`

## Reports Expected

- Per-run `results.jsonl`
- Per-run `summary.json`
- Per-run `REPORT.md`
- Project-level `scale-tests/RUNBOOK.md`

## Execution Constraint

This phase may run benchmarks. It must use synthetic data only and must label backend/model/hardware assumptions explicitly.
