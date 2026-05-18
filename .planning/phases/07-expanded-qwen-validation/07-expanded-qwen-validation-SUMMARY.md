# Phase 7: Expanded qwen2.5 Validation - Summary

**Status:** Complete with bounded validation
**Completed:** 2026-05-03

## Work Completed

- Diagnosed HTTP extension blocker: service launch path used a Python environment without uvicorn, then HTTP runner/service lifecycle remained unstable.
- Diagnosed qwen library benchmark failure: runner ignored environment config and fell back to missing default model llama3.
- Fixed scale-tests/run_library_benchmark.py to inherit Config.from_env().
- Ran corrected qwen2.5:7b library validation over 3 documents.
- Published scale-tests/reports/qwen25-7b-model-path-hardening.md.

## Result

- Corrected qwen library docs: 3
- qwen leak count: 0
- qwen detected name/date_of_birth/address: yes
- Current gate: pass for bounded local validation

## Deferred

A 40-document qwen HTTP extension remains deferred because the local service runner is unstable and qwen2.5:7b is slow on the currently visible RAM/CPU profile.
