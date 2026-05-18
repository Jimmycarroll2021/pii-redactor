# PII Redactor Scale-Test Report

Generated: 2026-04-30T21:35:48.295010+00:00
Status: NOT RUN

## Configuration

- Backend: http://127.0.0.1:8019
- Audit mode: n/a
- Documents: scale-tests\fixtures\synthetic-1000-seed42\documents.jsonl

## Throughput

- Total seconds: 0.0000
- Docs/sec: 0.00
- Estimated docs/day: 0.00

## Latency

- min: 0.0000 ms
- mean: 0.0000 ms
- median: 0.0000 ms
- p95: 0.0000 ms
- max: 0.0000 ms

## Correctness Signals

## Privacy Safety

- Leak checked total: 0
- Leak count total: 0

## Limitations

- Synthetic data proves repeatability and pipeline behavior, not real-world clinical recall.
- Mock backend measurements isolate deterministic regex and local pipeline overhead.
- Service-backed benchmarks should be run separately with the target local LLM backend and deployment hardware.
