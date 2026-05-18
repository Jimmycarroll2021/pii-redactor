# PII Redactor Scale-Test Report

Generated: 2026-05-01T21:38:29.561390+00:00
Status: OK

## Configuration

- Backend: http://127.0.0.1:8022
- Audit mode: n/a
- Documents: 20

## Throughput

- Total seconds: 277.4921
- Docs/sec: 0.07
- Estimated docs/day: 6,227.20

## Latency

- min: 72896.7467 ms
- mean: 118878.3093 ms
- median: 128803.2552 ms
- p95: 145009.9803 ms
- max: 145009.9803 ms

## Correctness Signals

## Privacy Safety

- Leak checked total: 320
- Leak count total: 0

## Limitations

- Synthetic data proves repeatability and pipeline behavior, not real-world clinical recall.
- Mock backend measurements isolate deterministic regex and local pipeline overhead.
- Service-backed benchmarks should be run separately with the target local LLM backend and deployment hardware.
