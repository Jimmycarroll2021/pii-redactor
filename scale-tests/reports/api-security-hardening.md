# API Security Hardening

**Generated:** 2026-05-03
**Phase:** 12 - API Security Hardening

## Verdict

Pass for production-style API authentication controls.

## Changes

- Added PIIR_REQUIRE_API_KEY=true startup enforcement.
- API key comparison now uses constant-time comparison.
- Added PIIR_REIDENTIFY_API_KEY support for /reidentify.
- /reidentify falls back to PIIR_API_KEY only when no separate re-identification key is configured.
- Local unauthenticated demo mode remains available when strict auth is disabled and no API key is set.

## Production Settings

`powershell
$env:PIIR_REQUIRE_API_KEY='true'
$env:PIIR_API_KEY='<redaction-api-key>'
$env:PIIR_REIDENTIFY_API_KEY='<separate-reidentify-key>'
`

## Remaining Security Work

- Secret storage/rotation outside environment variables.
- Role-based authorization around re-identification.
- Audit retention policy and incident response runbook.
- TLS and network boundary controls for hosted deployments.
