# Phase 1 Research: Scale-Test Evidence Baseline

## Research Question

What does the current project prove about PII redaction at scale, and what evidence is missing?

## Findings

### 1. The codebase is scale-ready, not scale-proven

The project has batch API support, concurrency controls, timing fields, and config hooks. Those are necessary for scale testing, but they are not proof of completed scale tests.

### 2. Historical artifacts are not recoverable from searched local paths

Searches across `KnowledgeGraph`, `Downloads`, `Pi-Sync`, `.claude`, and `.codex` found source code, old ZIPs, and unrelated batch artifacts. They did not find PII-specific scale reports, corpora, raw benchmark outputs, or large audit logs.

### 3. Future evidence must be project-local

The old working pattern likely used transient Downloads, agent logs, or scratch runs. Future scale testing should write durable artifacts under `scale-tests/` so results are discoverable and reproducible.

### 4. Correctness and privacy are first-class metrics

A throughput report alone is insufficient. The scale report must prove no original PII values appear in redacted outputs, safe spans, safe PII tables, or run logs.

## Planning Implication

Phase 1 should be a documentation and evidence-contract phase. Phase 2 should build corpus and harness. Phase 3 should run benchmarks and publish reports.
