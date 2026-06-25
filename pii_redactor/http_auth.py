"""Fail-closed HTTP auth policy (framework-agnostic, no web dependencies).

Separated from ``api/main.py`` so the security policy is unit-testable without
FastAPI installed, and so the same policy can back any transport.

VULN-04 / SEC-04 (Stage-1 hostile audit): auth is fail-closed by default. An
unset key NO LONGER silently disables auth — redaction and re-identification
reject unless the operator explicitly sets ``PIIR_ALLOW_NO_AUTH=true`` for
local-only use. Re-identification requires its own dedicated key and never
falls back to the redaction key.
"""

from __future__ import annotations

import os
import secrets
from collections.abc import Mapping

_TRUTHY = {"1", "true", "yes", "on"}


def _truthy(value: str | None) -> bool:
    return (value or "").lower() in _TRUTHY


def auth_disabled_ok(env: Mapping[str, str] = os.environ) -> bool:
    """True only when no-auth was explicitly opted into (local/dev)."""
    return _truthy(env.get("PIIR_ALLOW_NO_AUTH"))


def keys_match(provided: str, expected: str) -> bool:
    return secrets.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


def redaction_auth_error(provided: str, env: Mapping[str, str] = os.environ) -> str | None:
    """Return a 401 detail string, or None to allow. Fail-closed on missing key."""
    expected = env.get("PIIR_API_KEY")
    if not expected:
        if auth_disabled_ok(env):
            return None
        return (
            "API key required. Set PIIR_API_KEY, or set PIIR_ALLOW_NO_AUTH=true "
            "for explicit local-only use."
        )
    return None if keys_match(provided, expected) else "Invalid or missing X-API-Key header."


def reidentify_auth_error(provided: str, env: Mapping[str, str] = os.environ) -> str | None:
    """Return a 401 detail string, or None to allow.

    Requires a dedicated PIIR_REIDENTIFY_API_KEY; never falls back to the
    redaction key.
    """
    expected = env.get("PIIR_REIDENTIFY_API_KEY")
    if not expected:
        if auth_disabled_ok(env):
            return None
        return (
            "Re-identification API key required. Set PIIR_REIDENTIFY_API_KEY "
            "(separate from PIIR_API_KEY), or PIIR_ALLOW_NO_AUTH=true for "
            "explicit local-only use."
        )
    return (
        None if keys_match(provided, expected) else "Invalid or missing re-identification API key."
    )


def public_bind_without_auth(env: Mapping[str, str] = os.environ) -> bool:
    """True when a non-loopback bind is requested with neither a key nor opt-out."""
    return (
        _truthy(env.get("PIIR_PUBLIC_BIND"))
        and not env.get("PIIR_API_KEY")
        and not auth_disabled_ok(env)
    )
