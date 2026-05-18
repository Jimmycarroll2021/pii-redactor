# Phase 11: Calibration Review Pack - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning
**Mode:** Autonomous GSD context

<domain>
## Phase Boundary

Create a human-review pack generator for false-positive and false-negative calibration. The project needs reviewer-friendly redacted outputs, detected PII tables, and expected labels side by side.

</domain>

<decisions>
## Implementation Decisions

### Output format
Use Markdown plus JSONL so reviewers can inspect manually and downstream tools can ingest results.

### Backend
Default to mock for fast review pack generation, with backend override for qwen when a smaller high-quality review pass is needed.

### Scope
This phase creates the review mechanism and a small generated pack. It does not claim human review is complete.

</decisions>
