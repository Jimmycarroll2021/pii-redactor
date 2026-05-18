# Phase 9: Service Lifecycle Hardening - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning
**Mode:** Autonomous GSD context

<domain>
## Phase Boundary

Make the qwen FastAPI validation path repeatable by removing Python interpreter ambiguity and documenting correct benchmark URL usage.

</domain>

<decisions>
## Implementation Decisions

### Interpreter
Use the installed Python 3.12 executable because it has uvicorn available. Avoid plain python and the py launcher for long-running service startup.

### Service settings
Default to qwen2.5:7b, Ollama at 127.0.0.1:11434, API port 8020, max concurrency 1, audit disabled.

### Benchmark URL
The HTTP benchmark appends /redact/batch internally, so callers must pass the base URL only.

</decisions>
