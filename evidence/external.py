"""External evidence retrieval and correlation via Zetaris.

Bounded, read-only queries through validated templates. Every returned
record is normalized to a typed ExternalEvidence with full provenance.
Explicit unavailable/failed status when Zetaris is unreachable — the
investigation reports incompleteness instead of inventing corroboration.
"""

from __future__ import annotations

import hashlib
import logging
import math

from integrations.zetaris.client import (
    ZetarisClient,
    ZetarisError,
    ZetarisStatus,
    get_zetaris_client,
)
from models import ExternalEvidence, ExtractionResult, IntegrationStatus

logger = logging.getLogger("veriforge.evidence.external")

MAX_INDICATORS_PER_KIND = 10


def _evidence_id(kind: str, value: str, source: str) -> str:
    digest = hashlib.sha256(f"ext\0{kind}\0{value}\0{source}".encode()).hexdigest()[:16]
    return f"ext-{digest}"


def _safe_confidence(value: object) -> float:
    """Accept a bounded numeric score without allowing malformed provider data."""
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 1.0
    return confidence if math.isfinite(confidence) and 0.0 <= confidence <= 1.0 else 1.0


async def correlate_indicators(
    extraction: ExtractionResult,
    client: ZetarisClient | None = None,
) -> tuple[list[ExternalEvidence], IntegrationStatus]:
    """Correlate extracted indicators against Zetaris datasets.

    Returns (evidence, status). A successful zero-row query is explicitly
    represented as no corroborating records. Failed attempts never count as
    retrieval, and mixed outcomes are degraded rather than available.
    """
    client = client or get_zetaris_client(refresh=True)
    if client.status == ZetarisStatus.NOT_CONFIGURED:
        return [], IntegrationStatus(
            name="zetaris",
            status="not_configured",
            detail="Zetaris credentials or registered IOC datasource not configured",
        )

    evidence: list[ExternalEvidence] = []
    datasource = client.config.datasource
    # A configured client always has a datasource, but retain a non-sensitive
    # fallback for test doubles and defensive callers.
    source = f"zetaris:{datasource.relation}" if datasource else "zetaris:registered_ioc"
    attempted_queries = 0
    successful_queries = 0
    last_error: str | None = None
    values_seen = 0

    async def _lookup(kind: str, values: list[str]) -> None:
        nonlocal attempted_queries, successful_queries, last_error, values_seen
        for value in values[:MAX_INDICATORS_PER_KIND]:
            values_seen += 1
            try:
                # lookup_domain also normalises URL and email-domain values;
                # this guarantees a hostname match rather than matching paths.
                attempted_queries += 1
                result = await client.lookup_domain(value)
                if result.status != ZetarisStatus.AVAILABLE:
                    last_error = result.error or result.status.value
                    continue
                successful_queries += 1
                for row in result.rows:
                    evidence.append(
                        ExternalEvidence(
                            id=_evidence_id(kind, value, source),
                            kind=kind,
                            value=str(row.get("indicator_value") or value),
                            source=source,
                            record_id=str(row.get("record_id") or ""),
                            query_ref=result.query_ref,
                            retrieved_at=result.executed_at,
                            observed=True,
                            confidence=_safe_confidence(row.get("confidence", 1.0)),
                            matched_indicator=value,
                            tags=[str(t) for t in (row.get("tags") or [])] if isinstance(row.get("tags"), list) else [],
                        )
                    )
            except ZetarisError as exc:
                last_error = str(exc)
                logger.warning("Zetaris lookup failed for %s=%s: %s", kind, value, exc)

    await _lookup("domain", extraction.domains)
    await _lookup("url", extraction.urls)
    await _lookup("email", extraction.emails)

    if not values_seen:
        return evidence, IntegrationStatus(
            name="zetaris",
            status="ready",
            detail="No supported observable indicators were extracted; no external query was needed",
        )
    if successful_queries == 0:
        return evidence, IntegrationStatus(
            name="zetaris",
            status="failed",
            detail=last_error or "All required Zetaris enrichment queries failed",
        )
    status = "available" if successful_queries == attempted_queries else "degraded"
    outcome = "no corroborating records" if not evidence else f"{len(evidence)} record(s) correlated"
    return evidence, IntegrationStatus(
        name="zetaris",
        status=status,
        detail=(
            f"{successful_queries} successful retrieval query/queries of {attempted_queries} attempted; "
            f"{outcome}" + (f"; failures: {last_error}" if last_error else "")
        ),
    )
