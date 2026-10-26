"""External evidence retrieval and correlation via Zetaris.

Bounded, read-only queries through validated templates. Every returned
record is normalized to a typed ExternalEvidence with full provenance.
Explicit unavailable/failed status when Zetaris is unreachable — the
investigation reports incompleteness instead of inventing corroboration.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

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


def _dataset_for(kind: str) -> str:
    # Dataset names configurable per deployment; defaults follow the
    # zetaris getting-started open_data naming style.
    import os

    return os.getenv("ZETARIS_IOC_DATASET", "threat_indicators")


async def correlate_indicators(
    extraction: ExtractionResult,
    client: ZetarisClient | None = None,
) -> tuple[list[ExternalEvidence], IntegrationStatus]:
    """Correlate extracted indicators against Zetaris datasets.

    Returns (evidence, status). On any failure the status is explicit and
    evidence is empty — never fabricated.
    """
    client = client or get_zetaris_client(refresh=True)
    if client.status == ZetarisStatus.NOT_CONFIGURED:
        return [], IntegrationStatus(
            name="zetaris",
            status="not_configured",
            detail="ZETARIS_BASE_URL/ZETARIS_ORG_ID/credentials not set",
        )

    evidence: list[ExternalEvidence] = []
    dataset = _dataset_for("domain")
    queries_run = 0
    last_error: str | None = None

    async def _lookup(kind: str, values: list[str]) -> None:
        nonlocal queries_run, last_error
        for value in values[:MAX_INDICATORS_PER_KIND]:
            try:
                if kind == "domain":
                    result = await client.lookup_domain(value, dataset=dataset)
                elif kind == "url":
                    # URL lookup matches on the registered domain column
                    result = await client.lookup_domain(value, dataset=dataset)
                elif kind == "email":
                    result = await client.lookup_domain(value.split("@")[-1], dataset=dataset)
                else:
                    continue
                queries_run += 1
                if result.status != ZetarisStatus.AVAILABLE:
                    last_error = result.error or result.status.value
                    continue
                for row in result.rows:
                    retrieved_at = result.executed_at
                    evidence.append(
                        ExternalEvidence(
                            id=_evidence_id(kind, value, dataset),
                            kind=kind,
                            value=str(row.get("domain") or row.get("indicator") or value),
                            source=f"zetaris:{dataset}",
                            record_id=str(row.get("id") or row.get("record_id") or ""),
                            query_ref=result.query[:200],
                            retrieved_at=retrieved_at,
                            observed=True,
                            confidence=float(row.get("confidence", row.get("score", 1.0)) or 1.0),
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

    if queries_run == 0:
        return evidence, IntegrationStatus(
            name="zetaris",
            status="failed" if last_error else "unavailable",
            detail=last_error or "No Zetaris queries could be executed",
        )
    status = IntegrationStatus(
        name="zetaris",
        status="available",
        detail=f"{queries_run} queries executed, {len(evidence)} record(s) correlated",
    )
    return evidence, status
