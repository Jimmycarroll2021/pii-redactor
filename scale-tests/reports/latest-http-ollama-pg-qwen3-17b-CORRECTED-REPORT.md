# PII Redactor Scale-Test Report

Generated: 2026-05-02T01:32:02.043245+00:00
Status: PARTIAL

## Configuration

- Backend: http://127.0.0.1:8023
- Audit mode: n/a
- Documents: 40

## Throughput

- Total seconds: 348.6160
- Docs/sec: 0.11
- Estimated docs/day: 9,913.49

## Latency

- min: 66750.5798 ms
- mean: 137722.2600 ms
- median: 135936.8312 ms
- p95: 210906.8789 ms
- max: 210906.8789 ms

## Correctness Signals

## Privacy Safety

- Leak checked total: 640
- Leak count total: 3
- address: 1
- date_of_birth: 1
- name: 1

## Limitations

- Synthetic data proves repeatability and pipeline behavior, not real-world clinical recall.
- Mock backend measurements isolate deterministic regex and local pipeline overhead.
- Service-backed benchmarks should be run separately with the target local LLM backend and deployment hardware.
