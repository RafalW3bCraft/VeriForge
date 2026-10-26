"""API security tests: authorization on history, error sanitization."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("HMEM_DATA_DIR", str(tmp_path / "hmem"))
    with TestClient(app) as c:
        yield c


def test_history_open_when_no_api_key_configured(client, monkeypatch):
    monkeypatch.delenv("VERIFORGE_API_KEY", raising=False)
    resp = client.get("/api/v1/analyses")
    assert resp.status_code == 200


def test_history_requires_key_when_configured(client, monkeypatch):
    monkeypatch.setenv("VERIFORGE_API_KEY", "secret-key-123")
    # get_settings() is not cached; new env is picked up directly
    resp = client.get("/api/v1/analyses")
    assert resp.status_code == 401
    resp = client.get("/api/v1/analyses", headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401
    resp = client.get("/api/v1/analyses", headers={"X-API-Key": "secret-key-123"})
    assert resp.status_code == 200


def test_analyze_error_does_not_leak_internals(client, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("internal database path /secret/db location")

    monkeypatch.setattr("apps.api.main.analyze", boom)
    resp = client.post("/api/v1/analyze", json={"content": "test message content"})
    assert resp.status_code == 500
    body = resp.json()
    assert "/secret/db" not in str(body)
    assert body["error"]["message"] == "Analysis could not be completed"


def test_integrations_status_truthful(client):
    resp = client.get("/api/v1/integrations/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["zetaris"]["status"] in {"available", "unavailable", "failed", "not_configured"}
    assert data["hmem"]["status"] in {"available", "failed"}
