# Phase 9: Service Lifecycle Hardening - Plan

**Status:** Planned
**Mode:** Autonomous GSD

## Goal

Provide stable operator scripts for qwen FastAPI startup and HTTP validation.

## Tasks

1. Add a qwen API startup script.
2. Add a qwen HTTP validation runner script.
3. Update runbook with correct interpreter and URL semantics.
4. Update final readiness package and GSD state.

## Acceptance Criteria

- Operator can start API without relying on ambiguous python resolution.
- Operator can run HTTP validation with the correct base URL.
- Scripts use qwen2.5:7b and conservative concurrency by default.
