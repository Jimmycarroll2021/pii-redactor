# Phase 12: API Security Hardening - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning
**Mode:** Autonomous GSD context

<domain>
## Phase Boundary

Harden FastAPI authentication behavior for production-style operation without breaking local demo defaults.

</domain>

<decisions>
## Implementation Decisions

### Local default
Keep unauthenticated local development possible when PIIR_API_KEY is unset and strict auth is not enabled.

### Production strict mode
Add PIIR_REQUIRE_API_KEY=true so production deployments fail startup if no API key is configured.

### Re-identification separation
Allow PIIR_REIDENTIFY_API_KEY for /reidentify, falling back to PIIR_API_KEY only when no separate key is configured.

### Comparison
Use constant-time comparison for API keys.

</decisions>
