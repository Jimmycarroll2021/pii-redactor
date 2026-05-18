# PII Redactor Scale-Test Report

Generated: 2026-04-30T20:22:21.990154+00:00
Status: OK

## Configuration

- Backend: http://127.0.0.1:8017
- Audit mode: n/a
- Documents: 1000

## Throughput

- Total seconds: 0.8562
- Docs/sec: 1,167.95
- Estimated docs/day: 100,911,119.96

## Latency

- min: 58.6508 ms
- mean: 82.7219 ms
- median: 80.4402 ms
- p95: 106.9257 ms
- max: 128.3252 ms

## Correctness Signals

## Privacy Safety

- Leak checked total: 0
- Leak count total: 0

## Limitations

- Synthetic data proves repeatability and pipeline behavior, not real-world clinical recall.
- Mock backend measurements isolate deterministic regex and local pipeline overhead.
- Service-backed benchmarks should be run separately with the target local LLM backend and deployment hardware.
