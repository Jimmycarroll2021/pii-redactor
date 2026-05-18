# Requirements: PII Redactor Scale-Test Recovery

**Defined:** 2026-05-01
**Core Value:** Prove, with repeatable local artifacts, that PII redaction works correctly and safely at batch scale without leaking original PII downstream.

## v1 Requirements

### Evidence Baseline

- [ ] **EVID-01**: Maintainer can read a concise inventory of existing scale-related traces and missing artifacts.
- [ ] **EVID-02**: Maintainer can distinguish confirmed files from inferred capabilities.
- [ ] **EVID-03**: Project contains a stable artifact directory layout for future scale tests.

### Synthetic Corpus

- [ ] **CORP-01**: Developer can generate deterministic synthetic documents with configurable count and seed.
- [ ] **CORP-02**: Corpus includes AU identifiers: TFN, Medicare, ABN, ACN, driver licence, passport, CRN, phone, email, BSB/account.
- [ ] **CORP-03**: Corpus includes medical identifiers: patient ID, MRN/URN/hospital number, healthcare identifier, DOB, address, names.
- [ ] **CORP-04**: Corpus includes negative controls and invalid checksum values to measure false positives.
- [ ] **CORP-05**: Corpus writes expected PII labels separately from source documents for metric calculation.

### Scale Harness

- [ ] **HARN-01**: Developer can run direct library scale tests without starting an HTTP server.
- [ ] **HARN-02**: Developer can run HTTP `/redact/batch` scale tests against a configured local service.
- [ ] **HARN-03**: Harness supports document count, concurrency, backend, seed, and output directory parameters.
- [ ] **HARN-04**: Harness records backend, model, config, start/end time, machine/runtime metadata, and errors.

### Safety and Correctness Metrics

- [ ] **SAFE-01**: Report proves redacted output contains no expected original PII values.
- [ ] **SAFE-02**: Report proves returned spans and safe PII table contain no original PII values.
- [ ] **SAFE-03**: Report records expected-vs-detected counts by category.
- [ ] **SAFE-04**: Report records false negative and false positive samples using synthetic identifiers only.
- [ ] **SAFE-05**: Audit behavior is measured separately for audit disabled, metadata-only audit, and encrypted audit modes where possible.

### Performance Reporting

- [ ] **PERF-01**: Report includes total documents, total time, docs/sec, estimated docs/day, and error rate.
- [ ] **PERF-02**: Report includes latency percentiles: p50, p90, p95, p99.
- [ ] **PERF-03**: Report compares at least two concurrency settings for the same corpus size.
- [ ] **PERF-04**: Report writes JSONL raw results plus a Markdown summary.

### Documentation

- [ ] **DOCS-01**: README or dedicated scale-test runbook explains how to reproduce the tests.
- [ ] **DOCS-02**: Reports explicitly label assumptions and unavailable historical artifacts.
- [ ] **DOCS-03**: Project state records latest scale-test status and next action.

## v2 Requirements

### Advanced Benchmarking

- **ADV-01**: Compare mock, Ollama, HF, and llama.cpp backends on the same corpus.
- **ADV-02**: Add memory/CPU/GPU utilization sampling.
- **ADV-03**: Add long soak test mode for multi-hour runs.
- **ADV-04**: Add CI smoke benchmark with a small corpus.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real PII datasets | Unsafe and unnecessary for scale harness validation |
| Legal compliance certification | Requires legal review outside engineering scope |
| Cloud load testing by default | Keep v1 local and reproducible first |
| Recreating deleted historical files | Search found no concrete recoverable PII scale artifacts |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| EVID-01 | Phase 1 | Pending |
| EVID-02 | Phase 1 | Pending |
| EVID-03 | Phase 1 | Pending |
| CORP-01 | Phase 2 | Pending |
| CORP-02 | Phase 2 | Pending |
| CORP-03 | Phase 2 | Pending |
| CORP-04 | Phase 2 | Pending |
| CORP-05 | Phase 2 | Pending |
| HARN-01 | Phase 2 | Pending |
| HARN-02 | Phase 2 | Pending |
| HARN-03 | Phase 2 | Pending |
| HARN-04 | Phase 2 | Pending |
| SAFE-01 | Phase 3 | Pending |
| SAFE-02 | Phase 3 | Pending |
| SAFE-03 | Phase 3 | Pending |
| SAFE-04 | Phase 3 | Pending |
| SAFE-05 | Phase 3 | Pending |
| PERF-01 | Phase 3 | Pending |
| PERF-02 | Phase 3 | Pending |
| PERF-03 | Phase 3 | Pending |
| PERF-04 | Phase 3 | Pending |
| DOCS-01 | Phase 3 | Pending |
| DOCS-02 | Phase 3 | Pending |
| DOCS-03 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 24 total
- Mapped to phases: 24
- Unmapped: 0

---
*Requirements defined: 2026-05-01*
*Last updated: 2026-05-01 after initial GSD draft*
