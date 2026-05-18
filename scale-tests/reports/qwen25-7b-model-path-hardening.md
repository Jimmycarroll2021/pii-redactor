# qwen2.5:7b Model Path Hardening

**Generated:** 2026-05-03
**Phase:** 7 - Expanded qwen2.5 Validation
**Model:** qwen2.5:7b

## Verdict

Pass for bounded local validation after fixing the library benchmark configuration path.

The benchmark harness now inherits environment configuration, so PIIR_OLLAMA_MODEL=qwen2.5:7b is actually used instead of falling back to the missing default llama3 model.

## Evidence

| Run | Path | Documents | Leak count | Error count | Notes |
|---|---|---:|---:|---:|---|
| Corrected HTTP partial | scale-tests/runs/20260502-121821-http-ollama-qwen25-7b-10docs-c1-corrected | 22 | 0 | 0 | Existing corrected HTTP evidence; service runner became unstable during extension. |
| Corrected library qwen | scale-tests/runs/20260503-library-ollama-qwen25-7b-corrected-3docs | 3 | 0 | 0 | Confirms qwen2.5:7b path detects name, DOB, and address after config fix. |

## Key Fix

scale-tests/run_library_benchmark.py now starts from Config.from_env() and then overrides backend/audit fields. This preserves model, Ollama URL, timeout, retry, and other runtime settings.

## Runtime Observation

qwen2.5:7b is accurate in this bounded run but slow on this machine:

- Mean latency: 68142.61 ms/document
- Throughput: 0.0147 docs/second
- Estimated docs/day: 1268

A 40-document qwen run is feasible but not efficient interactively on this hardware. The project should keep qwen2.5:7b for high-quality local validation and use deterministic/mock gates for fast regression checks.

## Gate Outcome

- Environment model selection bug: fixed
- qwen2.5:7b library path: pass
- LLM-only value detection: pass
- Safe-payload leak count: pass
- Large corrected HTTP extension: deferred due service-runner instability and runtime cost
