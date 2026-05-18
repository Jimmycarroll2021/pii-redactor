# PII Redactor Scale-Test Report

Generated: 2026-05-02T07:06:28.344017+00:00
Status: OK

## Configuration

- Backend: http://127.0.0.1:8025
- Audit mode: n/a
- Documents: 20

## Throughput

- Total seconds: 453.4228
- Docs/sec: 0.04
- Estimated docs/day: 3,811.01

## Latency

- min: 80890.0465 ms
- mean: 92875.3631 ms
- median: 88797.7783 ms
- p95: 119414.0551 ms
- max: 119414.0551 ms

## Correctness Signals

## Privacy Safety

- Leak checked total: 320
- Leak count total: 0

## Limitations

- Synthetic data proves repeatability and pipeline behavior, not real-world clinical recall.
- Mock backend measurements isolate deterministic regex and local pipeline overhead.
- Service-backed benchmarks should be run separately with the target local LLM backend and deployment hardware.
