# PII Redactor Scale-Test Report

Generated: 2026-05-01T10:14:54.1498771Z
Status: FAILED_PARTIAL_RECOVERED

## Configuration

- Backend: http://127.0.0.1:8020
- Audit mode: n/a
- Documents: 65

## Throughput

- Total seconds: 910.9185
- Docs/sec: 0.07
- Estimated docs/day: 6,165.21

## Latency

- min: 58365.1471 ms
- mean: 130892.5547 ms
- median: 128432.6145 ms
- p95: 186511.7398 ms
- max: 186511.7398 ms

## Correctness Signals

## Privacy Safety

- Leak checked total: 0
- Leak count total: 0

## Limitations

- Synthetic data proves repeatability and pipeline behavior, not real-world clinical recall.
- Mock backend measurements isolate deterministic regex and local pipeline overhead.
- Service-backed benchmarks should be run separately with the target local LLM backend and deployment hardware.
