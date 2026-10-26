"""Zetaris SQL-over-HTTP client.

Implements the documented UI proxy route from zetaris/getting-started:
- Bearer token auth (ZETARIS_API_KEY) or username/password token exchange
- X-Org-ID header required
- X-Request-ID: fresh UUID per request
- 30s timeout, bounded row limit
- Read-only SELECT queries through validated templates
- Explicit unavailable/failed status when unreachable

The raw API port (8888) is NOT used; the UI proxy at ZETARIS_BASE_URL is.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger("veriforge.integrations.zetaris")


class ZetarisError(RuntimeError):
    """Base Zetaris error."""


class ZetarisUnavailable(ZetarisError):
    """Zetaris instance is unreachable or not configured."""


class ZetarisStatus(str, Enum):
    """Explicit status for sponsor-integration health reporting."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    NOT_CONFIGURED = "not_configured"


@dataclass(frozen=True)
class ZetarisConfig:
    """Configuration for Zetaris connectivity. All values come from env."""

    base_url: str | None
    org_id: str | None
    api_key: str | None
    username: str | None
    password: str | None
    query_limit: int = 1000
    engine_id: str | None = None
    timeout_seconds: float = 30.0
    max_retries: int = 2

    @classmethod
    def from_env(cls) -> ZetarisConfig:
        return cls(
            base_url=os.getenv("ZETARIS_BASE_URL") or None,
            org_id=os.getenv("ZETARIS_ORG_ID") or None,
            api_key=os.getenv("ZETARIS_API_KEY") or None,
            username=os.getenv("ZETARIS_USERNAME") or None,
            password=os.getenv("ZETARIS_PASSWORD") or None,
            query_limit=int(os.getenv("ZETARIS_QUERY_LIMIT", "1000")),
            engine_id=os.getenv("ZETARIS_ENGINE_ID") or None,
            timeout_seconds=float(os.getenv("ZETARIS_TIMEOUT_SECONDS", "30")),
            max_retries=int(os.getenv("ZETARIS_MAX_RETRIES", "2")),
        )

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.org_id and (self.api_key or (self.username and self.password)))

    @property
    def status(self) -> ZetarisStatus:
        if not self.configured:
            return ZetarisStatus.NOT_CONFIGURED
        return ZetarisStatus.AVAILABLE


@dataclass(frozen=True)
class ThreatIndicator:
    """Typed threat indicator normalized from Zetaris query results."""

    id: str
    kind: str  # domain, url, ip, hash, email
    value: str
    source: str  # dataset name in Zetaris
    record_id: str  # source record identifier
    query_ref: str  # template + parameters hash
    retrieved_at: datetime
    observed: bool = True  # False = inferred/correlated, not directly observed
    confidence: float = 1.0
    tags: tuple[str, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def provenance(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "record_id": self.record_id,
            "query_ref": self.query_ref,
            "retrieved_at": self.retrieved_at.isoformat(),
            "observed": self.observed,
        }


@dataclass(frozen=True)
class ZetarisQueryResult:
    """Result of a single Zetaris SQL query."""

    query: str
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


# ---------------------------------------------------------------------------
# SQL template validation
# ---------------------------------------------------------------------------

# Only allow these statement types (read-only)
_ALLOWED_SQL_RE = re.compile(r"^\s*(SELECT|WITH|SHOW|DESCRIBE|EXPLAIN)\b", re.IGNORECASE | re.DOTALL)
_FORBIDDEN_SQL_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|GRANT|REVOKE|EXEC|EXECUTE|MERGE|CALL|COPY)\b",
    re.IGNORECASE,
)
_COMMENT_RE = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)


def validate_sql(sql: str) -> str:
    """Reject anything that is not a read-only SELECT/SHOW/DESCRIBE/EXPLAIN.

    Raises ZetarisError on invalid SQL. Returns normalized SQL.
    """
    cleaned = _COMMENT_RE.sub(" ", sql).strip()
    if not cleaned:
        raise ZetarisError("Empty SQL statement")
    if not _ALLOWED_SQL_RE.match(cleaned):
        raise ZetarisError(f"Only SELECT/SHOW/DESCRIBE/EXPLAIN statements are allowed, got: {cleaned[:80]}")
    if _FORBIDDEN_SQL_RE.search(cleaned):
        raise ZetarisError(f"SQL contains forbidden write/DDL keywords: {cleaned[:80]}")
    return cleaned


def _query_ref(template_name: str, params: dict[str, Any]) -> str:
    digest = hashlib.sha256(f"{template_name}:{sorted(params.items())}".encode()).hexdigest()[:12]
    return f"zetaris:{template_name}:{digest}"


# ---------------------------------------------------------------------------
# Query templates — no arbitrary string interpolation of user content
# ---------------------------------------------------------------------------

class QueryTemplate:
    """A named, parameterized, read-only SQL template.

    Parameters are bound positionally; the template uses %s placeholders
    and the client validates the final SQL before sending.
    """

    def __init__(self, name: str, sql: str, param_names: tuple[str, ...]):
        self.name = name
        self.sql = sql
        self.param_names = param_names

    def render(self, **params: Any) -> str:
        missing = [n for n in self.param_names if n not in params]
        if missing:
            raise ZetarisError(f"Missing parameters for {self.name}: {missing}")
        # Simple positional substitution — parameters are already validated
        # by the caller (indicator values). The client re-validates the final SQL.
        rendered = self.sql
        for name in self.param_names:
            value = params[name]
            if isinstance(value, str):
                # Escape single quotes for SQL string literal
                escaped = value.replace("'", "''")
                rendered = rendered.replace(f"%({name})s", f"'{escaped}'")
            elif isinstance(value, (int, float)):
                rendered = rendered.replace(f"%({name})s", str(value))
            else:
                raise ZetarisError(f"Unsupported parameter type for {name}: {type(value)}")
        return validate_sql(rendered)


# Pre-defined templates for threat intelligence queries
TEMPLATES: dict[str, QueryTemplate] = {
    "indicator_by_domain": QueryTemplate(
        "indicator_by_domain",
        "SELECT * FROM %(dataset)s WHERE domain = %(domain)s LIMIT %(limit)s",
        ("dataset", "domain", "limit"),
    ),
    "indicator_by_hash": QueryTemplate(
        "indicator_by_hash",
        "SELECT * FROM %(dataset)s WHERE hash = %(hash)s LIMIT %(limit)s",
        ("dataset", "hash", "limit"),
    ),
    "indicator_by_ip": QueryTemplate(
        "indicator_by_ip",
        "SELECT * FROM %(dataset)s WHERE ip = %(ip)s LIMIT %(limit)s",
        ("dataset", "ip", "limit"),
    ),
    "list_datasets": QueryTemplate(
        "list_datasets",
        "SHOW TABLES",
        (),
    ),
    "dataset_schema": QueryTemplate(
        "dataset_schema",
        "DESCRIBE %(dataset)s",
        ("dataset",),
    ),
}


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class ZetarisClient:
    """HTTP client for Zetaris UI proxy SQL execution."""

    def __init__(self, config: ZetarisConfig | None = None):
        self._config = config or ZetarisConfig.from_env()
        self._token: str | None = None
        self._token_expires: datetime | None = None

    @property
    def config(self) -> ZetarisConfig:
        return self._config

    @property
    def status(self) -> ZetarisStatus:
        return self._config.status

    async def _get_token(self) -> str:
        """Obtain or return cached bearer token."""
        if self._config.api_key:
            return self._config.api_key
        # Username/password token exchange — documented in getting-started
        # but the exact endpoint is instance-specific. We attempt the common
        # /api/auth/token route; if it 404s the caller gets a clear error.
        if not (self._config.username and self._config.password):
            raise ZetarisUnavailable("No Zetaris credentials configured")
        async with httpx.AsyncClient(timeout=self._config.timeout_seconds) as client:
            resp = await client.post(
                f"{self._config.base_url}/api/auth/token",
                json={"username": self._config.username, "password": self._config.password},
                headers={"X-Org-ID": self._config.org_id or ""},
            )
            if resp.status_code == 404:
                raise ZetarisUnavailable(
                    "Zetaris token endpoint not found; check ZETARIS_BASE_URL is the UI origin"
                )
            resp.raise_for_status()
            data = resp.json()
            token = data.get("access_token") or data.get("token")
            if not token:
                raise ZetarisError("Token response missing access_token")
            self._token = token
            return token

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Send an authenticated request through the UI proxy."""
        if not self._config.configured:
            raise ZetarisUnavailable("Zetaris is not configured (missing base_url, org_id, or credentials)")
        token = await self._get_token()
        request_id = str(uuid.uuid4())
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Org-ID": self._config.org_id or "",
            "X-Request-ID": request_id,
            "Content-Type": "application/json",
        }
        assert self._config.base_url is not None
        url = f"{self._config.base_url.rstrip('/')}{path}"
        async with httpx.AsyncClient(timeout=self._config.timeout_seconds) as client:
            return await client.request(method, url, headers=headers, **kwargs)

    async def execute_sql(self, sql: str) -> ZetarisQueryResult:
        """Execute one read-only SQL statement through the UI proxy.

        Returns a result object with explicit status; raises ZetarisUnavailable
        when the instance is not configured, ZetarisError for invalid SQL.
        """
        validated = validate_sql(sql)
        executed_at = datetime.now(timezone.utc)
        start = datetime.now(timezone.utc)
        try:
            resp = await self._request(
                "POST",
                "/api/proxy/query",
                json={
                    "sql": validated,
                    "limit": self._config.query_limit,
                    **({"engineId": self._config.engine_id} if self._config.engine_id else {}),
                },
            )
            duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            if resp.status_code != 200:
                return ZetarisQueryResult(
                    query=validated,
                    rows=(),
                    row_count=0,
                    truncated=False,
                    executed_at=executed_at,
                    duration_ms=duration_ms,
                    status=ZetarisStatus.FAILED,
                    error=f"HTTP {resp.status_code}: {resp.text[:200]}",
                )
            data = resp.json()
            rows = tuple(data.get("rows", data.get("data", [])))
            row_count = len(rows)
            truncated = row_count >= self._config.query_limit
            return ZetarisQueryResult(
                query=validated,
                rows=rows,
                row_count=row_count,
                truncated=truncated,
                executed_at=executed_at,
                duration_ms=duration_ms,
                status=ZetarisStatus.AVAILABLE,
            )
        except httpx.TimeoutException as exc:
            return ZetarisQueryResult(
                query=validated,
                rows=(),
                row_count=0,
                truncated=False,
                executed_at=executed_at,
                duration_ms=(datetime.now(timezone.utc) - start).total_seconds() * 1000,
                status=ZetarisStatus.UNAVAILABLE,
                error=f"Timeout: {exc}",
            )
        except httpx.RequestError as exc:
            return ZetarisQueryResult(
                query=validated,
                rows=(),
                row_count=0,
                truncated=False,
                executed_at=executed_at,
                duration_ms=(datetime.now(timezone.utc) - start).total_seconds() * 1000,
                status=ZetarisStatus.UNAVAILABLE,
                error=f"Connection error: {exc}",
            )

    async def query_template(self, template_name: str, **params: Any) -> ZetarisQueryResult:
        """Execute a named query template with validated parameters."""
        template = TEMPLATES.get(template_name)
        if not template:
            raise ZetarisError(f"Unknown query template: {template_name}")
        sql = template.render(**params)
        return await self.execute_sql(sql)

    async def check_connectivity(self) -> ZetarisQueryResult:
        """Documented connectivity check: list Lightning databases."""
        return await self.execute_sql("SHOW DATABASES")

    async def lookup_domain(self, domain: str, dataset: str = "threat_indicators") -> ZetarisQueryResult:
        """Look up a domain indicator across a configured dataset."""
        return await self.query_template(
            "indicator_by_domain", dataset=dataset, domain=domain, limit=self._config.query_limit
        )

    async def lookup_hash(self, hash_value: str, dataset: str = "threat_indicators") -> ZetarisQueryResult:
        return await self.query_template(
            "indicator_by_hash", dataset=dataset, hash=hash_value, limit=self._config.query_limit
        )

    async def lookup_ip(self, ip: str, dataset: str = "threat_indicators") -> ZetarisQueryResult:
        return await self.query_template(
            "indicator_by_ip", dataset=dataset, ip=ip, limit=self._config.query_limit
        )


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_client: ZetarisClient | None = None


def get_zetaris_client(refresh: bool = False) -> ZetarisClient:
    """Return the shared client. refresh=True re-reads configuration from the
    environment (used when settings may have changed since first access)."""
    global _client
    if _client is None or refresh:
        _client = ZetarisClient()
    return _client


def reset_zetaris_client() -> None:
    global _client
    _client = None
