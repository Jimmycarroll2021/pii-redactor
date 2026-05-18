# qwen2.5:7b Expanded Library Validation

**Generated:** 2026-05-03
**Phase:** 10 - Expanded qwen Library Validation
**Backend:** Ollama
**Model:** qwen2.5:7b
**Run:** scale-tests/runs/20260503-library-ollama-qwen25-7b-corrected-4docs

## Verdict

Pass for the expanded bounded qwen validation gate.

## Results

| Metric | Value |
|---|---:|
| Documents | 4 |
| Status | OK |
| Safe-payload leak count | 0 |
| Mean latency ms | 59295.69 |
| Docs/sec | 0.0169 |
| Estimated docs/day | 1457 |

## Detection Coverage Observed

- name: 4
- date_of_birth: 4
- address: 4
- medical_record_number: 4
- healthcare_identifier: 4
- patient_id: 4

## Interpretation

qwen2.5:7b correctly contributed the LLM-only fields in this bounded validation pass and no checked PII values leaked into the safe output payload.

The model remains slow on this machine. Larger runs should be launched intentionally using the service lifecycle scripts and left to complete unattended.
