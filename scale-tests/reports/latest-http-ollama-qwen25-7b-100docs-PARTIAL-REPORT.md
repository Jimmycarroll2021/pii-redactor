# PII Redactor Scale-Test Report

Generated: 2026-04-30T21:52:56.2635023Z
Status: FAILED_PARTIAL_RECOVERED

## Configuration

- Backend: http://127.0.0.1:8019
- Audit mode: n/a
- Documents: 20

## Throughput

- Total seconds: 898.3422
- Docs/sec: 0.02
- Estimated docs/day: 1,923.54

## Latency

- min: 360383.5370 ms
- mean: 380832.4939 ms
- median: 360406.0617 ms
- p95: 442121.2410 ms
- max: 442121.2410 ms

## Correctness Signals

## Privacy Safety

- Leak checked total: 0
- Leak count total: 0

## Limitations

- Synthetic data proves repeatability and pipeline behavior, not real-world clinical recall.
- Mock backend measurements isolate deterministic regex and local pipeline overhead.
- Service-backed benchmarks should be run separately with the target local LLM backend and deployment hardware.
