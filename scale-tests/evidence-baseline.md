# Scale-Test Evidence Baseline

## Search outcome

No prior concrete scale-test artifact was found for the PII redactor project.

Searched areas included the consolidated `KnowledgeGraph` project tree, Downloads extraction folders and archived source zips, plus local agent/config folders where work products are commonly left.

## Evidence found

- Source-level batch support exists through the FastAPI `/redact/batch` endpoint.
- Config-level concurrency support exists via `PIIR_MAX_CONCURRENCY`.
- Existing tests cover hybrid detection, validators, and pipeline basics.
- Archived zips contain source/test material, not benchmark outputs.

## Evidence not found

- No large synthetic PII corpus.
- No benchmark harness.
- No JSONL/CSV scale result sets.
- No throughput or latency report.
- No saved audit trail from bulk de-identification runs.

## Project decision

Treat the historical scale-test work as unrecoverable and replace it with deterministic, reproducible artifacts in `scale-tests/`.

This avoids guessing from memory and creates a durable basis for future local-privacy evaluation.
