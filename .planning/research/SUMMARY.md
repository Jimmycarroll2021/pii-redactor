# Research Summary: PII Redactor Scale Testing

## Confirmed Existing Capability

- Python library pipeline can process documents directly.
- FastAPI app exposes `/redact` and `/redact/batch`.
- Batch endpoint uses semaphore-bounded concurrency via `PIIR_MAX_CONCURRENCY`.
- API response includes per-document `processing_ms`.
- Config supports backend selection, concurrency, audit path, and redaction style.
- Tests cover validators, hybrid regex/LLM detection, pipeline redaction, audit encryption, and regression cases.

## Missing Evidence

Search did not find concrete historical PII scale-test artifacts:

- no saved benchmark report
- no large generated synthetic corpus
- no PII-specific load-test script
- no large-run `audit.jsonl`
- no raw JSONL/CSV result files
- no throughput report tied to a completed run

## Planning Implication

The right project move is not to keep searching indefinitely. Preserve the search conclusion as an evidence baseline, then rebuild scale testing with stable artifact paths and reproducible commands.

## Technical Direction

- Generate synthetic corpora with known labels.
- Run direct library benchmarks for fast correctness and baseline throughput.
- Run HTTP batch benchmarks for concurrency/API behavior.
- Record raw results and summaries for every run.
- Add safety assertions that inspect redacted text, spans, PII table, and logs.

---
*Created: 2026-05-01*
