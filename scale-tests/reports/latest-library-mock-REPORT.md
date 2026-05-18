# PII Redactor Scale-Test Report

Generated: 2026-04-30T19:55:34.441648+00:00
Status: OK

## Configuration

- Backend: mock
- Audit mode: disabled
- Documents: 1000

## Throughput

- Total seconds: 0.6402
- Docs/sec: 1,562.13
- Estimated docs/day: 134,967,966.21

## Latency

- min: 0.5037 ms
- mean: 0.5612 ms
- median: 0.5311 ms
- p95: 0.6920 ms
- max: 1.2907 ms

## Correctness Signals

Expected valid labels:
- abn: 1000
- acn: 1000
- address: 1000
- bsb_account: 1000
- crn: 1000
- date_of_birth: 1000
- driver_licence: 1000
- email: 1000
- healthcare_identifier: 1000
- medical_record_number: 1000
- medicare: 1000
- name: 1000
- passport: 1000
- patient_id: 1000
- phone: 1000
- tfn: 1000

Detected labels:
- abn: 1000
- acn: 1000
- bsb_account: 2204
- centrelink_crn: 1000
- driver_licence: 899
- email: 1000
- healthcare_identifier: 1000
- medical_record_number: 1000
- medicare: 1100
- passport: 1000
- patient_id: 1000
- phone: 900
- tfn: 1101

## Privacy Safety

- Leak checked total: 13000
- Leak count total: 0

Scope note: Mock backend excludes name, address, and date_of_birth because those require LLM extraction; structured values remain checked.

## Limitations

- Synthetic data proves repeatability and pipeline behavior, not real-world clinical recall.
- Mock backend measurements isolate deterministic regex and local pipeline overhead.
- Service-backed benchmarks should be run separately with the target local LLM backend and deployment hardware.
