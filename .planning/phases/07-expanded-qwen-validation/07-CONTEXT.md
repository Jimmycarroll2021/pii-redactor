# Phase 7: Expanded qwen2.5 Validation - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning
**Mode:** Autonomous GSD context

<domain>
## Phase Boundary

Expand corrected qwen2.5:7b validation from the current 20-document gate to a larger corrected run. This improves confidence in model-backed de-PII behavior without changing the chosen local model.

</domain>

<decisions>
## Implementation Decisions

### Model
Use qwen2.5:7b through the existing local service/Ollama path because this is the chosen machine-fit model.

### Scale target
Resume the corrected benchmark to 40 documents. This keeps runtime bounded while doubling current corrected model evidence.

### Stop condition
Stop only if the service is unreachable, the run has errors, or structured safe-payload leaks appear.

</decisions>

<code_context>
## Existing Code Insights

The corrected qwen2.5:7b HTTP run already exists and has 20/20 documents processed with zero leaks. The HTTP benchmark supports --resume and corrected document_id payload semantics.

</code_context>

<specifics>
## Specific Ideas

Resume scale-tests/runs/20260502-121821-http-ollama-qwen25-7b-10docs-c1-corrected to --limit 40 using concurrency 1 and batch size 2.

</specifics>
