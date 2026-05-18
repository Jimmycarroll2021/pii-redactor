# Phase 3 Research: Scaled Runs and Reporting

## Research Summary

A trustworthy PII redaction benchmark report must include three linked views:

1. Performance: speed, concurrency, latency, errors.
2. Correctness: expected vs detected counts by category.
3. Privacy safety: proof that original PII does not appear in safe outputs.

## Report Design

Each run folder should contain:

- `run-config.json`: explicit command/config used.
- `results.jsonl`: raw per-document safe results.
- `summary.json`: aggregate metrics.
- `REPORT.md`: human-readable report.

## Minimum Benchmark Matrix

For v1:

- Direct library benchmark: 1k+ synthetic documents using mock backend.
- HTTP batch benchmark: same or smaller corpus at two concurrency settings if API service is available.

If HTTP service is unavailable, Phase 3 should write a blocked/skip note instead of silently passing.

## Safety Standard

A report is not acceptable unless it states:

- leak_count
- where leaks were checked
- whether audit mode was disabled/metadata/encrypted
- whether expected labels are synthetic fixtures

## Throughput Standard

Report:

- docs/sec
- estimated docs/day
- p50/p90/p95/p99 latency
- total errors
- backend/model/config

Avoid unqualified production claims unless the run environment matches production.
