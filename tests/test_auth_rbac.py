"""Focused local-account tests: sessions, CSRF and investigation isolation."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from apps.api.main import _login_limit_cache, _rate_limit_cache, app
from database import UserRecord, get_database
from engine import analyze


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/accounts.db")
    monkeypatch.setenv("HMEM_DATA_DIR", str(tmp_path / "hmem"))
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("VERIFORGE_BOOTSTRAP_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("VERIFORGE_BOOTSTRAP_ADMIN_PASSWORD", "correct-horse-battery-staple")
    monkeypatch.setenv("VERIFORGE_SESSION_COOKIE_SECURE", "false")
    get_database.cache_clear()
    _rate_limit_cache.clear()
    _login_limit_cache.clear()
    with TestClient(app) as test_client:
        yield test_client
    get_database.cache_clear()


def login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["csrf_token"]


def test_accounts_fail_closed_and_write_routes_require_csrf(client):
    assert client.get("/api/v1/analyses").status_code == 401
    assert client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong-password"}).status_code == 401

    csrf = login(client, "admin", "correct-horse-battery-staple")
    assert client.get("/api/v1/auth/me").json()["role"] == "admin"
    request = {"username": "analyst", "password": "another-long-password", "role": "analyst"}
    assert client.post("/api/v1/admin/users", json=request).status_code == 403
    assert client.post("/api/v1/admin/users", headers={"X-CSRF-Token": csrf}, json=request).status_code == 201


def test_analyst_cannot_access_admin_investigation_or_admin_routes(client):
    admin_csrf = login(client, "admin", "correct-horse-battery-staple")
    response = client.post(
        "/api/v1/admin/users",
        headers={"X-CSRF-Token": admin_csrf},
        json={"username": "analyst", "password": "another-long-password", "role": "analyst"},
    )
    assert response.status_code == 201

    # Seed an investigation owned by the bootstrap administrator.
    result = asyncio.run(analyze("Routine security notice."))
    database = get_database()
    with database._session_factory() as session:
        admin = session.query(UserRecord).filter_by(username="admin").one()
    database.save_analysis(result, tenant_id="legacy", owner_id=admin.user_id)

    analyst_client = TestClient(app)
    try:
        analyst_csrf = login(analyst_client, "analyst", "another-long-password")
        assert analyst_client.get("/api/v1/analyses").json()["items"] == []
        assert analyst_client.get(f"/api/v1/analyses/{result.analysis_id}").status_code == 404
        assert analyst_client.get("/api/v1/admin/users").status_code == 403
        # A valid session alone is insufficient for state changes without CSRF.
        assert analyst_client.post("/api/v1/analyses/unknown/review", json={"status": "open"}).status_code == 403
        assert analyst_csrf
    finally:
        analyst_client.close()
