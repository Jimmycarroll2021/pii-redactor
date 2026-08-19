"""Smoke tests for the engine FastAPI app (RUN-01 regression).

Verifies that ``api.main:app`` can be imported and starts regardless of whether
``PIIR_API_KEY`` is configured. The auth policy itself is tested in
``test_api_auth_failclosed.py``; this file catches import/startup regressions.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from pii_redactor import __version__


def _build_app(monkeypatch, *, api_key: str | None, allow_no_auth: bool = False) -> TestClient:
    """Import a fresh app instance with the requested auth env."""
    monkeypatch.delenv("PIIR_API_KEY", raising=False)
    monkeypatch.delenv("PIIR_ALLOW_NO_AUTH", raising=False)
    monkeypatch.delenv("PIIR_PUBLIC_BIND", raising=False)
    monkeypatch.delenv("PIIR_BACKEND", raising=False)
    monkeypatch.setenv("PIIR_BACKEND", "mock")
    if api_key is not None:
        monkeypatch.setenv("PIIR_API_KEY", api_key)
    if allow_no_auth:
        monkeypatch.setenv("PIIR_ALLOW_NO_AUTH", "true")

    # Import inside helper so env vars are already patched.
    from api.main import app

    return TestClient(app)


def test_app_starts_without_api_key(monkeypatch) -> None:
    client = _build_app(monkeypatch, api_key=None)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_app_starts_with_explicit_no_auth_optout(monkeypatch) -> None:
    client = _build_app(monkeypatch, api_key=None, allow_no_auth=True)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_info_matches_package_version(monkeypatch) -> None:
    client = _build_app(monkeypatch, api_key=None)
    response = client.get("/info")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == __version__
    assert data.get("backend") == "mock"


def test_redact_endpoint_rejects_when_no_key_and_no_optout(monkeypatch) -> None:
    client = _build_app(monkeypatch, api_key=None)
    response = client.post("/redact", json={"text": "Call me on 0412 345 678."})
    assert response.status_code == 401


def test_redact_endpoint_allows_with_key(monkeypatch) -> None:
    client = _build_app(monkeypatch, api_key="test-secret-key")
    response = client.post(
        "/redact",
        json={"text": "Call me on 0412 345 678."},
        headers={"X-API-Key": "test-secret-key"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "[REDACTED_PHONE" in data["redacted_text"] or "[REDACTED" in data["redacted_text"]
