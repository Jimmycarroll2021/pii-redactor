# Phase 2 Plan: Scale Harness and Synthetic Corpus

## Objective

Implement the reusable scale-test harness for `pii-redactor`: deterministic synthetic corpus generation, direct library benchmarking, and HTTP `/redact/batch` benchmarking.

## Deliverables

### 1. `scale-tests/generate_corpus.py`

Create a deterministic corpus generator.

Required CLI arguments:

- `--count N`
- `--seed N`
- `--out DIR`
- `--profile mixed|clinical|government|negative`

Required outputs:

- `documents.jsonl`: one synthetic document per line with `document_id`, `text`, and scenario metadata.
- `expected_labels.jsonl`: one label per line or per document with `document_id`, `category`, `value`, and optional offsets.
- `manifest.json`: generation config, timestamp, counts by category, seed, and profile.

Required synthetic categories:

- Names, DOBs, addresses, phone, email.
- TFN, Medicare, ABN, ACN, driver licence, passport, BSB/account, CRN.
- Patient ID, MRN/URN/hospital number, healthcare identifier.
- Invalid checksum controls for TFN, ABN, ACN, Medicare.

### 2. `scale-tests/run_library_benchmark.py`

Create direct pipeline benchmark runner.

Required CLI arguments:

- `--documents PATH`
- `--expected PATH`
- `--out DIR`
- `--backend mock|ollama|hf|llama_cpp`
- `--audit-mode disabled|metadata|encrypted`
- `--limit N` optional

Required behavior:

- Build a pipeline using project config/environment.
- Process documents sequentially first; concurrency can be added later only if safe.
- Measure per-document elapsed time.
- Write `results.jsonl` and `summary.json`.
- Include safe output fields only; expected originals are used internally for scoring.

### 3. `scale-tests/run_http_batch_benchmark.py`

Create HTTP benchmark runner for `/redact/batch`.

Required CLI arguments:

- `--documents PATH`
- `--expected PATH`
- `--url http://localhost:8000`
- `--batch-size N`
- `--concurrency N`
- `--out DIR`
- `--api-key KEY` optional
- `--limit N` optional

Required behavior:

- Chunk documents into batches.
- Send concurrent batch requests up to `--concurrency`.
- Preserve per-document result mapping.
- Fail clearly if API service is unavailable.
- Write raw and summary outputs in the same schema as the library benchmark where possible.

### 4. Fixture and Output Directories

Create:

- `scale-tests/fixtures/README.md`
- `scale-tests/runs/.gitkeep`
- `scale-tests/reports/.gitkeep`

## Summary Metrics Schema

`summary.json` should include:

- `run_id`
- `runner`: `library` or `http_batch`
- `document_count`
- `success_count`
- `error_count`
- `total_seconds`
- `docs_per_second`
- `estimated_docs_per_day`
- `latency_ms`: `min`, `p50`, `p90`, `p95`, `p99`, `max`
- `expected_pii_count`
- `detected_pii_count`
- `leak_count`
- `category_counts`
- `config`
- `errors`

## Safety Checks Required in Runners

For every result, compare expected synthetic values against:

- `redacted_text`
- returned `spans`
- returned `pii_table`
- serialized safe result line

Any match increments `leak_count` and records a synthetic-only leak sample.

## Verification Checklist

- [ ] Generator can create a small fixture corpus with deterministic output.
- [ ] Library runner can process generated fixture with mock backend.
- [ ] HTTP runner has clear CLI and service-unavailable failure path.
- [ ] Runners write `results.jsonl` and `summary.json`.
- [ ] Summary schema contains performance and safety fields.
- [ ] No real PII is introduced.

## Acceptance Criteria

Phase 2 is complete when a developer can generate a synthetic corpus and run at least the direct library benchmark against it without additional design work.

## Plan Status

Ready for `$gsd-execute-phase 2` after Phase 1 completes.
