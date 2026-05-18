# Phase 2 Context: Scale Harness and Synthetic Corpus

## Phase Goal

Build the repeatable machinery needed to prove PII redaction at scale: deterministic synthetic corpora, expected labels, direct-library benchmark runner, and HTTP `/redact/batch` benchmark runner.

## Requirements Covered

- CORP-01: deterministic synthetic documents with configurable count and seed.
- CORP-02: AU identifiers in corpus.
- CORP-03: medical identifiers in corpus.
- CORP-04: negative controls and invalid checksum values.
- CORP-05: expected labels separate from documents.
- HARN-01: direct library scale tests.
- HARN-02: HTTP `/redact/batch` scale tests.
- HARN-03: parameters for count, concurrency, backend, seed, output directory.
- HARN-04: metadata capture for backend, model, config, runtime, and errors.

## Relevant Existing Code

- `pii_redactor.pipeline.build_pipeline()` constructs direct library pipeline.
- `pii_redactor.config.Config` controls backend and audit settings.
- `api/main.py` exposes `/redact/batch` and per-document `processing_ms`.
- `pii_redactor.models.RedactionResult.to_dict()` returns redacted text, spans, and safe PII table.
- `pii_redactor.validators` contains checksum validators and regex first pass.

## Output Contract

Phase 2 should create:

- `scale-tests/generate_corpus.py`
- `scale-tests/run_library_benchmark.py`
- `scale-tests/run_http_batch_benchmark.py`
- `scale-tests/fixtures/README.md`
- `scale-tests/runs/.gitkeep`
- `scale-tests/reports/.gitkeep`

## Design Constraints

- Fixture data is synthetic only.
- Expected labels may contain synthetic originals, but benchmark reports must treat them as controlled test fixtures and not as production-safe output.
- Benchmark runners must never require a real API key by default.
- HTTP runner should fail clearly if the service is not running.
- Direct runner should work offline with the mock backend.
