"""Zetaris registered-datasource and transport contract tests."""

from __future__ import annotations

import json
import os

import httpx
import pytest

from evidence.external import correlate_indicators
from integrations.zetaris.client import (
    RegisteredDataSource,
    ZetarisClient,
    ZetarisConfig,
    ZetarisError,
    ZetarisStatus,
    ZetarisUnavailable,
    normalize_hostname,
    validate_identifier,
)
from models import ExtractionResult


def _config() -> ZetarisConfig:
    return ZetarisConfig(
        base_url="http://zetaris.local:3000",
        org_id="42",
        api_key="test-key",
        username=None,
        password=None,
        datasource=RegisteredDataSource(
            relation="approved.ioc_records",
            domain_column="domain_name",
            record_id_column="ioc_id",
            confidence_column="confidence_score",
            tags_column="labels",
        ),
        query_limit=25,
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("HTTPS://Example.COM.:443/path?q=1", "example.com"),
        ("analyst@Example.COM", "example.com"),
        ("bücher.example", "xn--bcher-kva.example"),
    ],
)
def test_normalize_hostname(raw, expected):
    assert normalize_hostname(raw) == expected


@pytest.mark.parametrize("value", ["", "127.0.0.1", "example.com; DROP TABLE x", "https://"])
def test_normalize_hostname_rejects_non_domains(value):
    with pytest.raises(ZetarisError):
        normalize_hostname(value)


@pytest.mark.parametrize("value", ["ioc.records", "public_ioc", "a.b.c.d"])
def test_registered_relation_allows_only_qualified_identifiers(value):
    assert validate_identifier(value, qualified=True) == value


@pytest.mark.parametrize("value", ["ioc;drop", "ioc records", "ioc.records;delete", "1invalid"])
def test_registered_relation_rejects_injection_identifiers(value):
    with pytest.raises(ZetarisError):
        validate_identifier(value, qualified=True)


def test_config_requires_explicit_registered_datasource(monkeypatch):
    for variable in (
        "ZETARIS_BASE_URL",
        "ZETARIS_ORG_ID",
        "ZETARIS_API_KEY",
        "ZETARIS_USERNAME",
        "ZETARIS_PASSWORD",
        "ZETARIS_IOC_DATASOURCE",
        "ZETARIS_IOC_DOMAIN_COLUMN",
        "ZETARIS_IOC_RECORD_ID_COLUMN",
    ):
        monkeypatch.delenv(variable, raising=False)
    config = ZetarisConfig.from_env()
    assert config.status == ZetarisStatus.NOT_CONFIGURED
    assert not config.configured


@pytest.mark.asyncio
async def test_client_refuses_unregistered_datasource():
    client = ZetarisClient(
        ZetarisConfig("http://zetaris.local", "42", "key", None, None, datasource=None)
    )
    with pytest.raises(ZetarisUnavailable):
        await client.lookup_domain("evil.example")


@pytest.mark.asyncio
async def test_lookup_uses_documented_transport_and_registered_projection(httpx_mock):
    httpx_mock.add_response(
        url="http://zetaris.local:3000/api/proxy/query/sql/start",
        method="POST",
        json={"rows": [{"indicator_value": "evil.example", "record_id": "ioc-1", "confidence": 0.9}]},
    )
    client = ZetarisClient(_config())
    result = await client.lookup_domain("https://EVIL.example/login")
    assert result.ok
    assert result.status == ZetarisStatus.AVAILABLE
    assert result.row_count == 1
    request = httpx_mock.get_request()
    body = json.loads(request.content)
    assert body["pageLimit"] == 25
    assert body["select"] == (
        "SELECT domain_name AS indicator_value, ioc_id AS record_id, "
        "confidence_score AS confidence, labels AS tags FROM approved.ioc_records "
        "WHERE domain_name = 'evil.example'"
    )
    assert request.headers["Authorization"] == "Bearer test-key"
    assert request.headers["X-Org-ID"] == "42"
    assert request.headers["X-Request-ID"]
    assert client.health()["data_returned"] is True


@pytest.mark.asyncio
async def test_password_identity_uses_participant_ui_login_contract(httpx_mock):
    config = ZetarisConfig(
        base_url="http://zetaris.local:3000",
        org_id="42",
        api_key=None,
        username="ioc-reader",
        password="not-a-real-secret",
        datasource=_config().datasource,
    )
    httpx_mock.add_response(
        url="http://zetaris.local:3000/api/auth/login",
        method="POST",
        json={"token": "test-session-token", "orgId": 42},
    )
    httpx_mock.add_response(
        url="http://zetaris.local:3000/api/proxy/query/sql/start",
        method="POST",
        json={"rows": []},
    )
    result = await ZetarisClient(config).lookup_domain("evil.example")
    assert result.status == ZetarisStatus.AVAILABLE
    requests = httpx_mock.get_requests()
    assert json.loads(requests[0].content) == {"username": "ioc-reader", "password": "not-a-real-secret"}
    assert requests[1].headers["Authorization"] == "Bearer test-session-token"


@pytest.mark.asyncio
async def test_empty_success_is_available_and_not_corroboration(httpx_mock):
    httpx_mock.add_response(
        url="http://zetaris.local:3000/api/proxy/query/sql/start", method="POST", json={"data": {"rows": []}}
    )
    client = ZetarisClient(_config())
    result = await client.lookup_domain("evil.example")
    assert result.ok and result.row_count == 0
    assert client.health()["data_returned"] is False


@pytest.mark.asyncio
async def test_malformed_provider_response_is_failed(httpx_mock):
    httpx_mock.add_response(
        url="http://zetaris.local:3000/api/proxy/query/sql/start", method="POST", json={"rows": [["not", "an object"]]}
    )
    result = await ZetarisClient(_config()).lookup_domain("evil.example")
    assert result.status == ZetarisStatus.FAILED
    assert result.error == "invalid_response"


@pytest.mark.asyncio
async def test_timeout_is_degraded_with_non_secret_failure_category(httpx_mock):
    httpx_mock.add_exception(
        httpx.TimeoutException("provider timeout"),
        url="http://zetaris.local:3000/api/proxy/query/sql/start",
        method="POST",
    )
    client = ZetarisClient(_config())
    result = await client.lookup_domain("evil.example")
    assert result.status == ZetarisStatus.DEGRADED
    assert result.error == "timeout"
    assert client.health()["failure_category"] == "timeout"


@pytest.mark.asyncio
async def test_correlation_counts_only_successful_queries_and_reports_zero_matches(httpx_mock):
    endpoint = "http://zetaris.local:3000/api/proxy/query/sql/start"
    httpx_mock.add_response(url=endpoint, method="POST", json={"rows": []})
    httpx_mock.add_response(url=endpoint, method="POST", status_code=503, text="upstream unavailable")
    evidence, status = await correlate_indicators(
        ExtractionResult(domains=["one.example", "two.example"]), client=ZetarisClient(_config())
    )
    assert evidence == []
    assert status.status == "degraded"
    assert "1 successful retrieval query/queries of 2 attempted" in status.detail
    assert "no corroborating records" in status.detail


@pytest.mark.asyncio
async def test_correlation_all_required_failures_is_incomplete_status(httpx_mock):
    httpx_mock.add_response(
        url="http://zetaris.local:3000/api/proxy/query/sql/start", method="POST", status_code=503, text="nope"
    )
    evidence, status = await correlate_indicators(
        ExtractionResult(domains=["one.example"]), client=ZetarisClient(_config())
    )
    assert evidence == []
    assert status.status == "failed"


@pytest.mark.asyncio
async def test_correlation_no_observables_is_ready_not_retrieved():
    evidence, status = await correlate_indicators(ExtractionResult(), client=ZetarisClient(_config()))
    assert evidence == []
    assert status.status == "ready"
    assert "no external query" in status.detail


# This acceptance test deliberately needs both a read-only identity and a
# registered, approved IOC mapping. It never reads a platform .env or falls
# back to a default datasource.
LIVE_REQUIRED = (
    "ZETARIS_BASE_URL",
    "ZETARIS_ORG_ID",
    "ZETARIS_IOC_DATASOURCE",
    "ZETARIS_IOC_DOMAIN_COLUMN",
    "ZETARIS_IOC_RECORD_ID_COLUMN",
    "ZETARIS_LIVE_TEST_HOSTNAME",
)
LIVE_CREDENTIALS_CONFIGURED = bool(
    os.getenv("ZETARIS_API_KEY")
    or (os.getenv("ZETARIS_USERNAME") and os.getenv("ZETARIS_PASSWORD"))
)
LIVE_CONFIGURED = (
    os.getenv("RUN_LIVE_ZETARIS_TESTS") == "1"
    and LIVE_CREDENTIALS_CONFIGURED
    and all(os.getenv(key) for key in LIVE_REQUIRED)
)


@pytest.mark.skipif(not LIVE_CONFIGURED, reason="live Zetaris read-only IOC acceptance configuration is not enabled")
@pytest.mark.asyncio
async def test_live_registered_datasource_normalized_lookup_contract():
    hostname = os.environ["ZETARIS_LIVE_TEST_HOSTNAME"]
    client = ZetarisClient()
    result = await client.lookup_domain(f"https://{hostname.upper()}/healthcheck")
    assert result.status == ZetarisStatus.AVAILABLE, result.error
    assert result.query_ref.startswith("zetaris:indicator_by_domain:")
    assert all("indicator_value" in row and "record_id" in row for row in result.rows)
    health = client.health()
    assert health["reachable"] is True
    assert health["last_query_outcome"] == "available"
