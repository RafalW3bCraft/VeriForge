"""Zetaris integration package.

SQL-over-HTTP client following the documented UI proxy route from
zetaris/getting-started (scripts/HOWTO.md). Read-only query templates,
typed evidence normalization, bounded results, controlled retries.
"""

from integrations.zetaris.client import (
    ZetarisClient,
    ZetarisConfig,
    ZetarisError,
    ZetarisUnavailable,
    ZetarisStatus,
    ZetarisQueryResult,
    ThreatIndicator,
    RegisteredDataSource,
    get_zetaris_client,
    normalize_hostname,
)

__all__ = [
    "ZetarisClient",
    "ZetarisConfig",
    "ZetarisError",
    "ZetarisUnavailable",
    "ZetarisStatus",
    "ZetarisQueryResult",
    "ThreatIndicator",
    "RegisteredDataSource",
    "get_zetaris_client",
    "normalize_hostname",
]
