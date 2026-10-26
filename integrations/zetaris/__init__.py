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
    get_zetaris_client,
)

__all__ = [
    "ZetarisClient",
    "ZetarisConfig",
    "ZetarisError",
    "ZetarisUnavailable",
    "ZetarisStatus",
    "ZetarisQueryResult",
    "ThreatIndicator",
    "get_zetaris_client",
]
