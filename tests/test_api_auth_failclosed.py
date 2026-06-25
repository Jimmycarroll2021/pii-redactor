"""Regression: HTTP auth policy is fail-closed by default (VULN-04 / SEC-04).

Tests the framework-agnostic policy in ``pii_redactor.http_auth`` (no FastAPI
dependency). With no key configured, redaction and re-identification reject
unless PIIR_ALLOW_NO_AUTH=true. /reidentify requires its own dedicated key and
never falls back to PIIR_API_KEY.
"""

from __future__ import annotations

from pii_redactor.http_auth import (
    public_bind_without_auth,
    redaction_auth_error,
    reidentify_auth_error,
)


def test_redaction_rejects_when_no_key_and_no_optout(monkeypatch) -> None:
    monkeypatch.delenv("PIIR_API_KEY", raising=False)
    monkeypatch.delenv("PIIR_ALLOW_NO_AUTH", raising=False)
    assert redaction_auth_error("") is not None  # fail-closed


def test_redaction_allows_when_explicit_optout(monkeypatch) -> None:
    monkeypatch.delenv("PIIR_API_KEY", raising=False)
    monkeypatch.setenv("PIIR_ALLOW_NO_AUTH", "true")
    assert redaction_auth_error("") is None


def test_redaction_enforces_key_when_set(monkeypatch) -> None:
    monkeypatch.setenv("PIIR_API_KEY", "s3cret")
    monkeypatch.delenv("PIIR_ALLOW_NO_AUTH", raising=False)
    assert redaction_auth_error("wrong") is not None
    assert redaction_auth_error("s3cret") is None


def test_reidentify_does_not_fall_back_to_redaction_key(monkeypatch) -> None:
    monkeypatch.setenv("PIIR_API_KEY", "s3cret")
    monkeypatch.delenv("PIIR_REIDENTIFY_API_KEY", raising=False)
    monkeypatch.delenv("PIIR_ALLOW_NO_AUTH", raising=False)
    # The redaction key must NOT unlock re-identification.
    assert reidentify_auth_error("s3cret") is not None


def test_reidentify_enforces_dedicated_key(monkeypatch) -> None:
    monkeypatch.setenv("PIIR_REIDENTIFY_API_KEY", "reidkey")
    monkeypatch.delenv("PIIR_ALLOW_NO_AUTH", raising=False)
    assert reidentify_auth_error("wrong") is not None
    assert reidentify_auth_error("reidkey") is None


def test_public_bind_without_auth_is_flagged(monkeypatch) -> None:
    monkeypatch.setenv("PIIR_PUBLIC_BIND", "true")
    monkeypatch.delenv("PIIR_API_KEY", raising=False)
    monkeypatch.delenv("PIIR_ALLOW_NO_AUTH", raising=False)
    assert public_bind_without_auth() is True
    monkeypatch.setenv("PIIR_API_KEY", "s3cret")
    assert public_bind_without_auth() is False
