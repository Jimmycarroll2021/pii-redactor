# Phase 6: Audit Mode Comparison - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning
**Mode:** Autonomous GSD context

<domain>
## Phase Boundary

Compare audit-disabled and audit-encrypted operation for the de-PII pipeline. The goal is to prove audit telemetry can be disabled for maximum privacy and, when enabled, stores encrypted redaction values without plaintext PII exposure.

</domain>

<decisions>
## Implementation Decisions

### Backend scope
Use the mock backend for this phase because audit behavior is independent from LLM extraction quality. Qwen model correctness is covered by the corrected qwen2.5:7b validation report.

### Audit security expectations
Disabled mode must not produce an audit log. Encrypted mode must produce audit rows with encrypted values and zero plaintext leaks for checked synthetic values.

### Human loop
Proceed autonomously unless a benchmark fails or audit output contains plaintext PII.

</decisions>

<code_context>
## Existing Code Insights

The library benchmark already processes deterministic synthetic documents and reports leak counts. It now needs to expose audit-log existence, line count, encrypted-value count, and plaintext leak count so audit posture can be gated.

</code_context>

<specifics>
## Specific Ideas

Run paired 20-document library benchmarks against the same synthetic fixture:

- audit disabled
- audit encrypted

Publish a comparison report under scale-tests/reports.

</specifics>

<deferred>
## Deferred Ideas

A larger qwen-backed audit run can be added later if the team wants a slower end-to-end model-plus-audit validation. This phase gates audit storage mechanics only.

</deferred>
