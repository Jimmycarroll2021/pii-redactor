"""Test security headers and CORS in the engine API (SEC-05)."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient


def test_security_headers_present_on_all_responses(monkeypatch):
    monkeypatch.setenv("PIIR_BACKEND", "mock")
    monkeypatch.delenv("PIIR_API_KEY", raising=False)
    monkeypatch.setenv("PIIR_ALLOW_NO_AUTH", "true")

    from api.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Content-Security-Policy"] == (
        "default-src 'none'; frame-ancestors 'none'"
    )
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "max-age=31536000" in response.headers["Strict-Transport-Security"]
