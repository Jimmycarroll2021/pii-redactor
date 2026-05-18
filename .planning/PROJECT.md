# PII Redactor Scale-Test Recovery

## What This Is

`pii-redactor` is a pre-ingestion PII de-identification service and Python library for Australian government and medical-style documents. It now has a reproducible local scale-test harness, deterministic synthetic corpus generation, benchmark runners, and a published mock-backend baseline report inside the KnowledgeGraph project.

## Core Value

The project must prove, with repeatable local artifacts, that PII redaction works correctly and safely at batch scale without leaking original PII downstream.

## Current State

v1.0 Scale Evidence is shipped and archived.

Delivered:

- Historical scale-test search was documented; prior concrete scale artifacts were not found.
- Canonical scale-test workspace was created under `scale-tests/`.
- Deterministic synthetic corpus generator was added.
- Direct library benchmark harness was added.
- FastAPI `/redact/batch` benchmark harness was added.
- A 1,000-document mock-backend benchmark was executed.
- Latest report is `scale-tests/reports/latest-library-mock-REPORT.md`.

Latest benchmark:

- Documents processed: 1,000
- Docs/sec: 1,562.13
- Estimated docs/day: 134,967,966
- Structured safe-payload leak count: 0

## Requirements

### Validated

- Evidence baseline exists for recovered and missing scale-test traces - v1.0.
- Scale-test artifacts now live under the project instead of Downloads/transient logs - v1.0.
- Synthetic corpus generation supports configurable count, seed, and profiles - v1.0.
- AU government and medical-document identifiers are included in generated fixtures - v1.0.
- Direct library processing can be benchmarked without starting HTTP - v1.0.
- HTTP `/redact/batch` benchmark tooling exists - v1.0.
- Reports include throughput, latency, category counts, and privacy leak checks - v1.0.
- Safe PII table behavior is included in downstream leak checking - v1.0.

### Active

- [ ] Run HTTP `/redact/batch` benchmark against a live FastAPI service.
- [ ] Run benchmarks against the target local LLM backend and hardware.
- [ ] Compare at least two HTTP concurrency settings.
- [ ] Compare audit disabled, metadata-only, and encrypted audit modes.
- [ ] Add explicit false-negative and false-positive samples to reports.
- [ ] Capture machine/runtime metadata for stronger performance evidence.

### Out of Scope

- Real citizen, patient, or customer data - unsafe and unnecessary for repeatable scale tests.
- Legal certification of Privacy Act or health-record compliance - this project provides technical evidence, not legal signoff.
- Reconstructing deleted artifacts from unavailable storage - document absence clearly and rebuild reproducibly.

## Context

The project was consolidated into `C:\Users\j_car\KnowledgeGraph\tools\pii-redactor`. The NEJM AI LLM-Anonymizer paper remains under `docs/references/AIdbp2400537.pdf` and grounds the local de-identification approach.

v1.0 recovered the project evidence trail and created reproducible benchmark infrastructure. The current baseline is mock-backend/direct-library only; it proves local harness behavior and structured safe-payload leak checks, not production LLM throughput.

## Constraints

- **Privacy**: Scale tests must use synthetic PII only.
- **Reproducibility**: Every run must write inputs, config, summary metrics, and report under a stable project directory.
- **No secret leakage**: Reports must never include API keys, audit keys, or real original PII values.
- **Backend variability**: Mock, Ollama, HF, and llama.cpp have different throughput characteristics; reports must record backend and model.
- **Evidence discipline**: Missing historical artifacts must be marked missing, not inferred as passed.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Keep scale-test artifacts inside `scale-tests/` under the project | Prevents future loss in Downloads or transient agent logs | Good - implemented v1.0 |
| Use synthetic generated PII for load tests | Provides repeatable coverage without real personal data | Good - implemented v1.0 |
| Report both correctness and performance | Fast redaction is not useful if PII leaks | Good - implemented v1.0 |
| Separate library benchmark from HTTP batch benchmark | Direct pipeline and API concurrency test different bottlenecks | Good - harnesses implemented v1.0 |
| Treat old scale-test artifacts as not found | Search did not reveal concrete saved PII scale-run outputs | Good - documented v1.0 |
| Carry real local-LLM/HTTP benchmarking into v1.1 | Requires live service/backend/hardware beyond mock baseline | Pending |

## Next Milestone Goals

v1.1 should turn the harness into higher-fidelity evidence by running service-backed benchmarks against the real configured local backend and comparing concurrency plus audit modes.

---
*Last updated: 2026-04-30 after v1.0 Scale Evidence milestone*
