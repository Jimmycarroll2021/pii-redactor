# Phase 12: API Security Hardening - Plan

**Status:** Planned
**Mode:** Autonomous GSD

## Goal

Improve API authentication controls for production readiness.

## Tasks

1. Add strict auth environment gate.
2. Use constant-time key comparison.
3. Add separate re-identification key support.
4. Update docs and final readiness package.

## Acceptance Criteria

- PIIR_REQUIRE_API_KEY=true fails startup without PIIR_API_KEY.
- /redact and /redact/batch still use PIIR_API_KEY.
- /reidentify can use PIIR_REIDENTIFY_API_KEY.
- Local unauthenticated demo mode remains possible by default.
