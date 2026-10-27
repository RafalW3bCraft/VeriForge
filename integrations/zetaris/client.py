"""Safe, bounded Zetaris IOC correlation client.

The browser-facing Zetaris SQL proxy is intentionally treated as a narrow
transport, not as a general SQL API. VeriForge only submits fixed read-only
statements against an explicitly registered IOC datasource. Indicator values
are normalised before being placed in a SQL literal and datasource identifiers
are accepted only after strict identifier validation.

The documented UI transport is ``POST /api/proxy/query/sql/start`` with a
``select`` statement and ``pageLimit``. The raw Zetaris API is never used.
"""

from __future__ import annotations

import hashlib
import ipaddress
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping
from urllib.parse import urlsplit

import httpx

MAX_QUERY_LIMIT = 250
DEFAULT_QUERY_LIMIT = 100
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_QUALIFIED_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*){0,3}$")
_HOST_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


class ZetarisError(RuntimeError):
    """Base Zetaris integration error safe to present as a failure category."""


class ZetarisUnavailable(ZetarisError):
    """Zetaris is not configured or cannot be reached."""


class ZetarisStatus(str, Enum):
    """Integration contract states, from configuration through query outcome."""

    NOT_CONFIGURED = "not_configured"
    READY = "ready"
    CONNECTING = "connecting"
    AVAILABLE = "available"
    DEGRADED = "degraded"
    FAILED = "failed"


def _bounded_int(value: str | None, *, default: int, name: str) -> int:
    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ZetarisError(f"{name} must be an integer") from exc
    if not 1 <= parsed <= MAX_QUERY_LIMIT:
        raise ZetarisError(f"{name} must be between 1 and {MAX_QUERY_LIMIT}")
    return parsed


def _bounded_float(value: str | None, *, default: float, name: str) -> float:
    if value in (None, ""):
        return default
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ZetarisError(f"{name} must be a number") from exc
    if not 1 <= parsed <= 60:
        raise ZetarisError(f"{name} must be between 1 and 60 seconds")
    return parsed


def validate_identifier(value: str, *, qualified: bool = False) -> str:
    """Return a safe datasource/column identifier, never quoted user input."""
    candidate = value.strip()
    pattern = _QUALIFIED_IDENTIFIER if qualified else _IDENTIFIER
    if not pattern.fullmatch(candidate):
        kind = "qualified identifier" if qualified else "identifier"
        raise ZetarisError(f"Invalid Zetaris {kind}")
    return candidate


def normalize_hostname(value: str) -> str:
    """Normalise a URL, host, or email-domain value for exact IOC lookup."""
    candidate = value.strip()
    if not candidate:
        raise ZetarisError("Hostname is empty")
    if "@" in candidate and "://" not in candidate:
        candidate = candidate.rsplit("@", 1)[1]
    parsed = urlsplit(candidate if "://" in candidate else f"//{candidate}")
    hostname = parsed.hostname
    if not hostname:
        raise ZetarisError("Hostname is invalid")
    hostname = hostname.rstrip(".").casefold()
    if not hostname or len(hostname) > 253:
        raise ZetarisError("Hostname is invalid")
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise ZetarisError("Expected a hostname, not an IP address")
    try:
        hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ZetarisError("Hostname is invalid") from exc
    if any(not _HOST_LABEL.fullmatch(label) for label in hostname.split(".")):
        raise ZetarisError("Hostname is invalid")
    return hostname


def _sql_literal(value: str) -> str:
    """Quote a validated indicator for a fixed statement template.

    Zetaris' documented ``sql/start`` transport accepts ``select`` text rather
    than a parameter array. Values are validated at the boundary and encoded as
    a SQL literal; they never influence identifiers or SQL structure.
    """
    return "'" + value.replace("'", "''") + "'"


@dataclass(frozen=True)
class RegisteredDataSource:
    """Approved IOC datasource and field mapping supplied by deployment config.

    There is intentionally no default dataset. An operator must register the
    approved source through runtime variables before corroboration is attempted.
    """

    relation: str
    domain_column: str
    record_id_column: str
    confidence_column: str | None = None
    tags_column: str | None = None

    @classmethod
    def from_env(cls) -> RegisteredDataSource | None:
        relation = os.getenv("ZETARIS_IOC_DATASOURCE")
        domain_column = os.getenv("ZETARIS_IOC_DOMAIN_COLUMN")
        record_id_column = os.getenv("ZETARIS_IOC_RECORD_ID_COLUMN")
        if not any((relation, domain_column, record_id_column)):
            return None
        if not all((relation, domain_column, record_id_column)):
            raise ZetarisError(
                "ZETARIS_IOC_DATASOURCE, ZETARIS_IOC_DOMAIN_COLUMN, and "
                "ZETARIS_IOC_RECORD_ID_COLUMN must be configured together"
            )
        confidence = os.getenv("ZETARIS_IOC_CONFIDENCE_COLUMN") or None
        tags = os.getenv("ZETARIS_IOC_TAGS_COLUMN") or None
        return cls(
            relation=validate_identifier(relation, qualified=True),
            domain_column=validate_identifier(domain_column),
            record_id_column=validate_identifier(record_id_column),
            confidence_column=validate_identifier(confidence) if confidence else None,
            tags_column=validate_identifier(tags) if tags else None,
        )

    def select_projection(self) -> str:
        fields = [
            f"{self.domain_column} AS indicator_value",
            f"{self.record_id_column} AS record_id",
        ]
        if self.confidence_column:
            fields.append(f"{self.confidence_column} AS confidence")
        if self.tags_column:
            fields.append(f"{self.tags_column} AS tags")
        return ", ".join(fields)


@dataclass(frozen=True)
class ZetarisConfig:
    """Non-secret Zetaris transport configuration sourced from runtime env."""

    base_url: str | None
    org_id: str | None
    api_key: str | None
    username: str | None
    password: str | None
    datasource: RegisteredDataSource | None = None
    query_limit: int = DEFAULT_QUERY_LIMIT
    engine_id: str | None = None
    timeout_seconds: float = 30.0
    max_retries: int = 0

    @classmethod
    def from_env(cls) -> ZetarisConfig:
        return cls(
            base_url=os.getenv("ZETARIS_BASE_URL") or None,
            org_id=os.getenv("ZETARIS_ORG_ID") or None,
            api_key=os.getenv("ZETARIS_API_KEY") or None,
            username=os.getenv("ZETARIS_USERNAME") or None,
            password=os.getenv("ZETARIS_PASSWORD") or None,
            datasource=RegisteredDataSource.from_env(),
            query_limit=_bounded_int(
                os.getenv("ZETARIS_QUERY_LIMIT"), default=DEFAULT_QUERY_LIMIT, name="ZETARIS_QUERY_LIMIT"
            ),
            engine_id=os.getenv("ZETARIS_ENGINE_ID") or None,
            timeout_seconds=_bounded_float(
                os.getenv("ZETARIS_TIMEOUT_SECONDS"), default=30.0, name="ZETARIS_TIMEOUT_SECONDS"
            ),
        )

    @property
    def connectivity_configured(self) -> bool:
        return bool(self.base_url and self.org_id and (self.api_key or (self.username and self.password)))

    @property
    def configured(self) -> bool:
        return self.connectivity_configured and self.datasource is not None

    @property
    def status(self) -> ZetarisStatus:
        return ZetarisStatus.READY if self.configured else ZetarisStatus.NOT_CONFIGURED


@dataclass(frozen=True)
class ThreatIndicator:
    id: str
    kind: str
    value: str
    source: str
    record_id: str
    query_ref: str
    retrieved_at: datetime
    observed: bool = True
    confidence: float = 1.0
    tags: tuple[str, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class ZetarisQueryResult:
    """Typed result of one registered query; empty rows are a valid success."""

    query_ref: str
    rows: tuple[dict[str, Any], ...]
    row_count: int
    truncated: bool
    executed_at: datetime
    duration_ms: float
    status: ZetarisStatus
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == ZetarisStatus.AVAILABLE and self.error is None


def _query_ref(template_name: str, params: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(repr((template_name, sorted(params.items()))).encode()).hexdigest()[:12]
    return f"zetaris:{template_name}:{digest}"


def _parse_rows(payload: Any) -> tuple[dict[str, Any], ...]:
    """Parse only the documented row forms; malformed results are failures."""
    if not isinstance(payload, Mapping):
        raise ZetarisError("Zetaris response was not a JSON object")
    # The documented UI proxy returns records under ``records``; accept the
    # common alternates for compatibility with other Zetaris deployments.
    rows: Any = payload.get("rows")
    if rows is None:
        rows = payload.get("records")
    if rows is None and isinstance(payload.get("data"), Mapping):
        rows = payload["data"].get("rows")
        if rows is None:
            rows = payload["data"].get("records")
    if rows is None:
        raise ZetarisError("Zetaris response did not include rows")
    if not isinstance(rows, list):
        raise ZetarisError("Zetaris response rows must be an array")
    parsed: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping) or not all(isinstance(key, str) for key in row):
            raise ZetarisError("Zetaris response rows must be objects with string keys")
        parsed.append(dict(row))
    return tuple(parsed)


class ZetarisClient:
    """HTTP client that executes only registered datasource templates."""

    def __init__(self, config: ZetarisConfig | None = None):
        self._config = config or ZetarisConfig.from_env()
        self._token: str | None = None
        self._last_status = self._config.status
        self._last_error: str | None = None
        self._last_query_at: datetime | None = None
        self._last_data_returned: bool | None = None

    @property
    def config(self) -> ZetarisConfig:
        return self._config

    @property
    def status(self) -> ZetarisStatus:
        return self._last_status

    def health(self) -> dict[str, Any]:
        """Non-secret integration contract for a health endpoint or caller."""
        return {
            "status": self.status.value,
            "configured": self._config.configured,
            "authenticated": bool(self._config.api_key or (self._config.username and self._config.password)),
            "reachable": self._last_status in {ZetarisStatus.AVAILABLE, ZetarisStatus.DEGRADED},
            "last_query_outcome": self._last_status.value if self._last_query_at else None,
            "data_returned": self._last_data_returned,
            "last_query_at": self._last_query_at.isoformat() if self._last_query_at else None,
            "failure_category": self._last_error,
        }

    async def _get_token(self) -> str:
        if self._config.api_key:
            return self._config.api_key
        if self._token:
            return self._token
        if not (self._config.username and self._config.password):
            raise ZetarisUnavailable("No Zetaris credentials configured")
        assert self._config.base_url is not None
        async with httpx.AsyncClient(timeout=self._config.timeout_seconds) as client:
            response = await client.post(
                # The participant platform's browser UI exposes this login
                # route. It returns a bearer token consumed by the SQL proxy;
                # do not guess a raw API endpoint or use the local platform's
                # administrator environment file.
                f"{self._config.base_url.rstrip('/')}/api/auth/login",
                json={"username": self._config.username, "password": self._config.password},
                headers={"Content-Type": "application/json"},
            )
        if response.status_code == 404:
            raise ZetarisUnavailable("Zetaris login endpoint not found")
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as exc:
            raise ZetarisError("Token response was not valid JSON") from exc
        # The platform's UI login returns the bearer token as ``idToken``;
        # accept the other common shapes for compatibility.
        token = (
            payload.get("idToken") or payload.get("access_token") or payload.get("token")
        ) if isinstance(payload, Mapping) else None
        if not isinstance(token, str) or not token:
            raise ZetarisError("Token response missing access token")
        self._token = token
        return token

    async def _request(self, select: str) -> httpx.Response:
        if not self._config.configured:
            raise ZetarisUnavailable("Zetaris IOC datasource or credentials are not configured")
        token = await self._get_token()
        self._last_status = ZetarisStatus.CONNECTING
        assert self._config.base_url is not None
        payload: dict[str, Any] = {"select": select, "pageLimit": self._config.query_limit}
        if self._config.engine_id:
            payload["engineId"] = self._config.engine_id
        async with httpx.AsyncClient(timeout=self._config.timeout_seconds) as client:
            return await client.post(
                f"{self._config.base_url.rstrip('/')}/api/proxy/query/sql/start",
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Org-ID": self._config.org_id or "",
                    "X-Request-ID": str(uuid.uuid4()),
                    "Content-Type": "application/json",
                },
            )

    def _domain_select(self, hostname: str) -> str:
        datasource = self._config.datasource
        if datasource is None:
            raise ZetarisUnavailable("No registered Zetaris IOC datasource")
        return (
            f"SELECT {datasource.select_projection()} FROM {datasource.relation} "
            f"WHERE {datasource.domain_column} = {_sql_literal(hostname)}"
        )

    async def _execute_registered(
        self, *, template_name: str, select: str, params: Mapping[str, Any]
    ) -> ZetarisQueryResult:
        executed_at = datetime.now(timezone.utc)
        started_at = executed_at
        query_ref = _query_ref(template_name, params)
        try:
            response = await self._request(select)
            duration_ms = (datetime.now(timezone.utc) - started_at).total_seconds() * 1000
            if response.status_code != 200:
                return self._result_failure(query_ref, executed_at, duration_ms, ZetarisStatus.FAILED, f"http_{response.status_code}")
            try:
                rows = _parse_rows(response.json())
            except (ValueError, ZetarisError):
                return self._result_failure(query_ref, executed_at, duration_ms, ZetarisStatus.FAILED, "invalid_response")
            result = ZetarisQueryResult(query_ref, rows, len(rows), len(rows) >= self._config.query_limit, executed_at, duration_ms, ZetarisStatus.AVAILABLE)
            self._record(result)
            return result
        except httpx.TimeoutException:
            return self._result_failure(query_ref, executed_at, (datetime.now(timezone.utc) - started_at).total_seconds() * 1000, ZetarisStatus.DEGRADED, "timeout")
        except httpx.RequestError:
            return self._result_failure(query_ref, executed_at, (datetime.now(timezone.utc) - started_at).total_seconds() * 1000, ZetarisStatus.DEGRADED, "connection_error")
        except ZetarisUnavailable:
            raise

    def _result_failure(self, query_ref: str, executed_at: datetime, duration_ms: float, status: ZetarisStatus, error: str) -> ZetarisQueryResult:
        result = ZetarisQueryResult(query_ref, (), 0, False, executed_at, duration_ms, status, error)
        self._record(result)
        return result

    def _record(self, result: ZetarisQueryResult) -> None:
        self._last_status = result.status
        self._last_error = result.error
        self._last_query_at = result.executed_at
        self._last_data_returned = bool(result.rows) if result.ok else None

    async def lookup_domain(self, domain: str) -> ZetarisQueryResult:
        """Look up a normalised hostname in the one registered IOC source."""
        hostname = normalize_hostname(domain)
        return await self._execute_registered(template_name="indicator_by_domain", select=self._domain_select(hostname), params={"hostname": hostname})

    async def check_connectivity(self) -> ZetarisQueryResult:
        """Probe the configured read-only IOC source without enumerating metadata."""
        datasource = self._config.datasource
        if datasource is None:
            raise ZetarisUnavailable("No registered Zetaris IOC datasource")
        return await self._execute_registered(
            template_name="ioc_connectivity_probe",
            select=f"SELECT {datasource.record_id_column} AS record_id FROM {datasource.relation}",
            params={},
        )


_client: ZetarisClient | None = None


def get_zetaris_client(refresh: bool = False) -> ZetarisClient:
    global _client
    if _client is None or refresh:
        _client = ZetarisClient()
    return _client


def reset_zetaris_client() -> None:
    global _client
    _client = None
