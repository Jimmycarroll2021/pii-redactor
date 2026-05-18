# Phase 1 Context: Scale-Test Evidence Baseline

## Phase Goal

Create durable project evidence for the PII scale-test state before rebuilding the harness. This phase does not run benchmarks. It records what was found, what was missing, and where all future scale artifacts must live.

## Known Inputs

- Project root: `C:\Users\j_car\KnowledgeGraph\tools\pii-redactor`
- Planning root: `.planning/`
- Correct project moved from Downloads into KnowledgeGraph tools.
- NEJM AI LLM-Anonymizer reference PDF is stored at `docs/references/AIdbp2400537.pdf`.
- Existing code supports direct pipeline processing and FastAPI `/redact/batch`.
- Search did not find concrete historical PII scale-test artifacts.

## Existing Scale-Related Code Traces

- `api/main.py` exposes `/redact/batch`.
- `api/main.py` records per-document `processing_ms`.
- `api/main.py` uses `PIIR_MAX_CONCURRENCY` through a semaphore.
- `pii_redactor/config.py` exposes backend, concurrency, audit, chunking, and redaction settings.
- `README.md` discusses batch integration and estimated scale targets.

## Missing Historical Artifacts

No concrete saved artifacts were found for:

- large generated synthetic PII corpus
- historical benchmark runner scripts
- HTTP batch load-test reports
- direct-library throughput reports
- raw JSONL/CSV benchmark output
- large-run `audit.jsonl`
- latency percentile reports
- historical pass/fail verification summaries

## Phase 1 Output Contract

Phase 1 should produce:

- `scale-tests/README.md`: canonical artifact layout and naming rules.
- `scale-tests/evidence-baseline.md`: confirmed traces, missing artifacts, and rebuild decision.
- `.planning/STATE.md`: updated to show Phase 1 completion and Phase 2 next action.

## Non-Goals

- Do not generate corpora in Phase 1.
- Do not run benchmarks in Phase 1.
- Do not claim historical scale tests passed.
- Do not create or process real PII.
