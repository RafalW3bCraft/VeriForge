"""Zetaris client unit tests (mocked HTTP) + live test gated on env."""

from __future__ import annotations

import os

import pytest

from integrations.zetaris.client import (
    QueryTemplate,
    TEMPLATES,
    ZetarisClient,
    ZetarisConfig,
    ZetarisError,
    ZetarisStatus,
    ZetarisUnavailable,
    validate_sql,
)


def test_validate_sql_allows_select():
    assert validate_sql("SELECT * FROM t WHERE x = 1").startswith("SELECT")


def test_validate_sql_allows_show_describe():
    assert validate_sql("SHOW TABLES")
    assert validate_sql("DESCRIBE my_table")
    assert validate_sql("WITH x AS (SELECT 1) SELECT * FROM x")


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO t VALUES (1)",
        "UPDATE t SET x = 1",
        "DELETE FROM t",
        "DROP TABLE t",
        "CREATE TABLE t (x int)",
        "ALTER TABLE t ADD COLUMN x int",
        "SELECT 1; DROP TABLE t",
        "GRANT SELECT ON t TO u",
    ],
)
def test_validate_sql_rejects_writes(sql):
    with pytest.raises(ZetarisError):
        validate_sql(sql)


def test_validate_sql_rejects_empty():
    with pytest.raises(ZetarisError):
        validate_sql("   -- just a comment")


def test_template_render_escapes_quotes():
    t = QueryTemplate("t", "SELECT * FROM d WHERE v = %(v)s LIMIT %(n)s", ("v", "n"))
    sql = t.render(v="o'reilly", n=5)
    assert "o''reilly" in sql
    assert "LIMIT 5" in sql


def test_template_missing_param_raises():
    t = TEMPLATES["indicator_by_domain"]
    with pytest.raises(ZetarisError):
        t.render(dataset="x")  # missing domain and limit


def test_config_not_configured_by_default(monkeypatch):
    for var in ("ZETARIS_BASE_URL", "ZETARIS_ORG_ID", "ZETARIS_API_KEY", "ZETARIS_USERNAME", "ZETARIS_PASSWORD"):
        monkeypatch.delenv(var, raising=False)
    config = ZetarisConfig.from_env()
    assert config.status == ZetarisStatus.NOT_CONFIGURED
    assert not config.configured


@pytest.mark.asyncio
async def test_client_unavailable_when_not_configured(monkeypatch):
    for var in ("ZETARIS_BASE_URL", "ZETARIS_ORG_ID", "ZETARIS_API_KEY", "ZETARIS_USERNAME", "ZETARIS_PASSWORD"):
        monkeypatch.delenv(var, raising=False)
    client = ZetarisClient(ZetarisConfig.from_env())
    with pytest.raises(ZetarisUnavailable):
        await client.execute_sql("SELECT 1")


@pytest.mark.asyncio
async def test_execute_sql_mocked(httpx_mock, monkeypatch):
    monkeypatch.setenv("ZETARIS_BASE_URL", "http://zetaris.local:3000")
    monkeypatch.setenv("ZETARIS_ORG_ID", "42")
    monkeypatch.setenv("ZETARIS_API_KEY", "test-key")
    httpx_mock.add_response(
        url="http://zetaris.local:3000/api/proxy/query",
        method="POST",
        json={"rows": [{"domain": "evil.example", "score": 0.9}]},
    )
    client = ZetarisClient(ZetarisConfig.from_env())
    result = await client.execute_sql("SELECT * FROM threat_indicators WHERE domain = 'evil.example'")
    assert result.ok
    assert result.status == ZetarisStatus.AVAILABLE
    assert result.row_count == 1
    assert result.rows[0]["domain"] == "evil.example"
    request = httpx_mock.get_request()
    assert request.headers["Authorization"] == "Bearer test-key"
    assert request.headers["X-Org-ID"] == "42"
    assert request.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_execute_sql_http_error_status(httpx_mock, monkeypatch):
    monkeypatch.setenv("ZETARIS_BASE_URL", "http://zetaris.local:3000")
    monkeypatch.setenv("ZETARIS_ORG_ID", "42")
    monkeypatch.setenv("ZETARIS_API_KEY", "test-key")
    httpx_mock.add_response(
        url="http://zetaris.local:3000/api/proxy/query",
        method="POST",
        status_code=500,
        text="boom",
    )
    client = ZetarisClient(ZetarisConfig.from_env())
    result = await client.execute_sql("SELECT 1")
    assert result.status == ZetarisStatus.FAILED
    assert not result.ok
    assert result.error is not None and "500" in result.error


@pytest.mark.asyncio
async def test_execute_sql_timeout_reports_unavailable(httpx_mock, monkeypatch):
    import httpx as httpx_lib

    monkeypatch.setenv("ZETARIS_BASE_URL", "http://zetaris.local:3000")
    monkeypatch.setenv("ZETARIS_ORG_ID", "42")
    monkeypatch.setenv("ZETARIS_API_KEY", "test-key")
    httpx_mock.add_exception(httpx_lib.TimeoutException("slow"), url="http://zetaris.local:3000/api/proxy/query")
    client = ZetarisClient(ZetarisConfig.from_env())
    result = await client.execute_sql("SELECT 1")
    assert result.status == ZetarisStatus.UNAVAILABLE


@pytest.mark.asyncio
async def test_injection_attempt_rejected(monkeypatch):
    monkeypatch.setenv("ZETARIS_BASE_URL", "http://zetaris.local:3000")
    monkeypatch.setenv("ZETARIS_ORG_ID", "42")
    monkeypatch.setenv("ZETARIS_API_KEY", "k")
    client = ZetarisClient(ZetarisConfig.from_env())
    with pytest.raises(ZetarisError):
        await client.execute_sql("SELECT * FROM t; DROP TABLE t")


# ---------------------------------------------------------------------------
# Live integration test — only runs when ZETARIS_BASE_URL is configured.
# Skipped otherwise; never claimed as passed when skipped.
# ---------------------------------------------------------------------------

LIVE_CONFIGURED = bool(os.getenv("ZETARIS_BASE_URL") and os.getenv("ZETARIS_ORG_ID"))


@pytest.mark.skipif(not LIVE_CONFIGURED, reason="ZETARIS_BASE_URL/ZETARIS_ORG_ID not configured")
@pytest.mark.asyncio
async def test_zetaris_live_connectivity():
    client = ZetarisClient()
    result = await client.check_connectivity()
    assert result.status == ZetarisStatus.AVAILABLE, f"Live Zetaris check failed: {result.error}"
    assert result.ok
