# PII Redactor Scale-Test Report

Generated: 2026-04-30T20:24:38.411286+00:00
Status: OK

## Configuration

- Backend: http://127.0.0.1:8018
- Audit mode: n/a
- Documents: 25

## Throughput

- Total seconds: 44.4960
- Docs/sec: 0.56
- Estimated docs/day: 48,543.67

## Latency

- min: 12842.7235 ms
- mean: 16778.0367 ms
- median: 15442.1789 ms
- p95: 23955.4582 ms
- max: 23955.4582 ms

## Correctness Signals

## Privacy Safety

- Leak checked total: 0
- Leak count total: 0

## Limitations

- Synthetic data proves repeatability and pipeline behavior, not real-world clinical recall.
- Mock backend measurements isolate deterministic regex and local pipeline overhead.
- Service-backed benchmarks should be run separately with the target local LLM backend and deployment hardware.
