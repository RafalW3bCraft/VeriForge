"""VeriForge investigation pipeline v2.

Flow (bounded, with failure handling):
 1. Screen input for prompt injection; mark trust.
 2. Extract claims and observable indicators.
 3. Create explicit investigation hypotheses.
 4. Retrieve external evidence from Zetaris (bounded, read-only).
 5. Retrieve relevant trusted H-MEM context.
 6. Run specialist reasoning against assembled evidence.
 7. Verify claims, supporting evidence, contradictions.
 8. Bounded additional retrieval when evidence is missing.
 9. Deterministic risk (outside the LLM), gated on verification support.
10. Evidence-linked explanation and recommended action.
11. Persist results, memory updates, telemetry.

High-impact facts carry typed evidence references; inferences are labeled.
On sponsor or provider failure the investigation reports incomplete status
instead of inventing outcomes.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
import logging

from config import get_settings
from evidence.extractor import extract_claims
from evidence.external import correlate_indicators
from evidence.graph import build_evidence_graph
from evidence.risk import calculate_risk
from evidence.sanitize import screen_content, sanitize_snippet
from agents.identity import run_identity
from agents.infrastructure import run_infrastructure
from agents.social_engineering import run_social_engineering
from agents.verifier import run_verifier
from hmem.engine import get_hmem_engine
from hmem.models import Entity, MemoryLayer, MemoryType, ProvenanceOrigin
from models import (
    AnalysisResponse,
    Hypothesis,
    InputType,
    IntegrationStatus,
    MemoryTrace,
    RiskDecision,
)

logger = logging.getLogger("veriforge.engine")

MAX_PIPELINE_STEPS = 11
MAX_HYPOTHESES = 8
MAX_MEMORY_CONTEXT = 5


def _build_hypotheses(extraction) -> list[Hypothesis]:
    """Explicit, falsifiable investigation hypotheses from extracted signals."""
    hypotheses: list[Hypothesis] = []
    if extraction.domains:
        hypotheses.append(
            Hypothesis(
                id=f"hyp-{len(hypotheses)+1}",
                statement=f"Domain(s) {', '.join(extraction.domains[:3])} are associated with known threat indicators",
                kind="infrastructure",
            )
        )
    if extraction.requests_credentials:
        hypotheses.append(
            Hypothesis(
                id=f"hyp-{len(hypotheses)+1}",
                statement="Message attempts credential harvesting",
                kind="social_engineering",
            )
        )
    if extraction.requests_financial_action:
        hypotheses.append(
            Hypothesis(
                id=f"hyp-{len(hypotheses)+1}",
                statement="Message attempts fraudulent financial action",
                kind="financial",
            )
        )
    if extraction.emails:
        hypotheses.append(
            Hypothesis(
                id=f"hyp-{len(hypotheses)+1}",
                statement="Sender identity is impersonated or spoofed",
                kind="identity",
            )
        )
    return hypotheses[:MAX_HYPOTHESES]


def _resolve_hypotheses(hypotheses, verification, external_evidence) -> None:
    """Mark hypotheses supported/contradicted/unverified from verification output."""
    for hyp in hypotheses:
        matched_ext = [
            e.id for e in external_evidence
            if (e.matched_indicator or e.value).casefold() in hyp.statement.casefold()
        ]
        if matched_ext:
            hyp.outcome = "supported"
            hyp.evidence_ids = matched_ext
        elif any(hyp.kind in m.casefold() for m in verification.missing_evidence):
            hyp.outcome = "unverified"
        elif hyp.kind in {f.source for f in verification.findings}:
            hyp.outcome = "supported"
        else:
            hyp.outcome = "unverified"


async def analyze(
    content: str,
    input_type: InputType = "message",
    context: dict[str, Any] | None = None,
) -> AnalysisResponse:
    context = context or {}
    settings = get_settings()
    steps: list[str] = []
    integration_status: list[IntegrationStatus] = []
    incomplete = False
    incomplete_reasons: list[str] = []
    analysis_id = str(uuid4())
    tenant_id = str(context.get("tenant_id") or "default")

    def _step(name: str) -> None:
        if len(steps) < MAX_PIPELINE_STEPS:
            steps.append(name)

    # 1. Screen input for prompt injection (attacker-controlled content)
    screening = screen_content(content)
    _step(f"input_screened:{screening.trust}")
    if screening.flagged:
        logger.warning("Prompt-injection patterns detected: %s", screening.patterns)

    # 2. Extract claims and indicators
    extraction = extract_claims(content)
    _step("claims_extracted")

    # 3. Hypotheses
    hypotheses = _build_hypotheses(extraction)
    _step("hypotheses_created")

    # 4. External evidence via Zetaris (bounded, read-only, failure-aware)
    external_evidence, zetaris_status = await correlate_indicators(extraction)
    integration_status.append(zetaris_status)
    _step(f"external_evidence:{zetaris_status.status}:{len(external_evidence)}")
    if zetaris_status.status not in {"available", "not_configured"}:
        incomplete = True
        incomplete_reasons.append(f"Zetaris {zetaris_status.status}: {zetaris_status.detail}")

    # 5. Trusted H-MEM context
    memory_traces: list[MemoryTrace] = []
    try:
        hmem = get_hmem_engine()
        recall_query = " ".join(
            [sanitize_snippet(content, 300)]
            + extraction.domains
            + extraction.urls
            + extraction.emails
        )
        investigation_id = str(context.get("investigation_id") or analysis_id)
        recall = hmem.recall(
            recall_query,
            tenant_id=tenant_id,
            investigation_id=investigation_id,
            top_n=MAX_MEMORY_CONTEXT,
        )
        for memory, trace in zip(recall.memories, recall.traces):
            memory_traces.append(
                MemoryTrace(
                    memory_id=memory.id,
                    content=sanitize_snippet(memory.content),
                    relevance_score=trace.relevance_score,
                    retrieval_reason=trace.retrieval_reason,
                    strategy=trace.strategy,
                    source=memory.source,
                    provenance_label=memory.provenance.label,
                    layer=memory.layer.value,
                    confidence=memory.confidence,
                    from_investigation_id=memory.investigation_id,
                )
            )
        health = hmem.health()
        integration_status.append(
            IntegrationStatus(
                name="hmem",
                status="available" if health["status"] == "available" else "failed",
                detail=f"{health.get('memories', {})}",
            )
        )
    except Exception:  # noqa: BLE001 — memory failure must not break analysis
        logger.exception("H-MEM retrieval failed")
        integration_status.append(
            IntegrationStatus(name="hmem", status="failed", detail="memory retrieval failed")
        )
        incomplete = True
        incomplete_reasons.append("H-MEM memory retrieval failed")
    _step(f"memory_context:{len(memory_traces)}")

    # 6. Specialist reasoning against assembled evidence
    agent_context = dict(context)
    agent_context["external_evidence"] = [e.model_dump(mode="json") for e in external_evidence]
    agent_context["memory_traces"] = [t.model_dump(mode="json") for t in memory_traces]
    agent_context["input_trust"] = screening.trust

    identity = await run_identity(extraction, agent_context)
    infrastructure = await run_infrastructure(extraction, agent_context)
    social = await run_social_engineering(extraction, content, agent_context)
    _step("specialists_complete")

    combined = {
        "extraction": extraction.model_dump(mode="json"),
        "agents": {
            "identity": identity.model_dump(mode="json"),
            "infrastructure": infrastructure.model_dump(mode="json"),
            "social_engineering": social.model_dump(mode="json"),
        },
        "external_evidence": [e.model_dump(mode="json") for e in external_evidence],
    }

    # 7. Verification
    verification = await run_verifier(combined, agent_context)
    _step("verification_complete")

    # 8. Bounded additional retrieval if evidence is missing
    if verification.missing_evidence and zetaris_status.status == "available" and not external_evidence:
        retry_evidence, _retry_status = await correlate_indicators(extraction)
        if retry_evidence:
            external_evidence = retry_evidence
            combined["external_evidence"] = [e.model_dump(mode="json") for e in external_evidence]
            verification = await run_verifier(combined, agent_context)
            _step("bounded_retrieval_retry:hit")
        else:
            _step("bounded_retrieval_retry:empty")

    # 9. Deterministic risk (outside LLM), gated on verification
    score = calculate_risk(identity, infrastructure, social, verification)

    verdict = (
        "CRITICAL" if score >= 85 else
        "HIGH" if score >= 70 else
        "SUSPICIOUS" if score >= 45 else
        "LOW" if score >= 20 else
        "SAFE"
    )

    if incomplete and verdict in {"CRITICAL", "HIGH"}:
        # Never emit a top-severity verdict on an incomplete investigation
        verdict = "SUSPICIOUS"
        score = min(score, 69.9)

    action = (
        "Do not click, respond, transfer money, or provide credentials. Verify through a trusted channel."
        if score >= 70 else
        "Pause and independently verify the sender, destination, and requested action."
        if score >= 45 else
        "Proceed only after normal security checks."
    )
    _step("risk_calculated")

    # 10. Evidence-linked explanation
    _resolve_hypotheses(hypotheses, verification, external_evidence)

    findings = (
        identity.findings
        + infrastructure.findings
        + social.findings
        + verification.findings
    )

    risk_decision = RiskDecision(
        risk_score=score,
        confidence=verification.confidence,
        evidence_strength=verification.evidence_strength,
        verdict=verdict,
        recommended_action=action,
    )
    graph = build_evidence_graph(
        extraction,
        {
            "identity": identity,
            "infrastructure": infrastructure,
            "social_engineering": social,
            "verification": verification,
        },
        risk_decision,
    )

    # 11. Persist memory updates (trusted findings only)
    try:
        hmem = get_hmem_engine()
        indicator_text = " ".join(extraction.domains + extraction.urls + extraction.emails)
        hmem.remember(
            content=(
                f"Investigation {analysis_id}: {verdict} (score {score}) — "
                f"{sanitize_snippet(verification.summary, 160)} "
                f"Indicators: {sanitize_snippet(indicator_text, 200)}"
            ),
            tenant_id=tenant_id,
            investigation_id=analysis_id,
            type=MemoryType.FACTUAL,
            layer=MemoryLayer.WORKING,
            source="veriforge:investigation",
            provenance_label=f"Verdict of investigation {analysis_id}",
            provenance_origin=ProvenanceOrigin.INVESTIGATION,
            provenance_refs=(analysis_id,),
            confidence=verification.confidence,
            tags=(verdict.lower(), input_type),
            entities=tuple(
                Entity(name=d, entity_type="domain") for d in extraction.domains[:5]
            ),
        )
        # High-trust external corroboration promotes to shared long-term knowledge
        if screening.trust == "trusted":
            for evidence in external_evidence:
                if evidence.confidence >= 0.7:
                    hmem.remember(
                        content=(
                            f"Indicator {evidence.value} corroborated by {evidence.source} "
                            f"(matched {evidence.matched_indicator})"
                        ),
                        tenant_id=tenant_id,
                        investigation_id=None,  # shared tenant knowledge
                        type=MemoryType.FACTUAL,
                        layer=MemoryLayer.LONG_TERM,
                        source=evidence.source,
                        provenance_label=f"Zetaris corroboration in {analysis_id}",
                        provenance_origin=ProvenanceOrigin.INVESTIGATION,
                        provenance_refs=(analysis_id, evidence.record_id),
                        confidence=evidence.confidence,
                        tags=("ioc", "corroborated"),
                        entities=(Entity(name=evidence.value, entity_type=evidence.kind),),
                    )
        hmem.scan_conflicts(tenant_id=tenant_id, investigation_id=analysis_id)
    except Exception:  # noqa: BLE001 — memory write failure must not break analysis
        logger.exception("H-MEM memory update failed")
    _step("memory_updated")

    return AnalysisResponse(
        analysis_id=analysis_id,
        created_at=datetime.now(timezone.utc),
        input_type=input_type,
        score=score,
        verdict=verdict,
        confidence=verification.confidence,
        risk_decision=risk_decision,
        summary=verification.summary,
        recommended_action=action,
        extraction=extraction,
        findings=findings,
        agents={
            "identity": identity,
            "infrastructure": infrastructure,
            "social_engineering": social,
            "verification": verification,
        },
        graph=graph,
        meta={
            "mode": "demo" if settings.demo_mode else "featherless",
            "principle": "LLM reasoning operates on evidence; risk is computed separately.",
            "input_trust": screening.trust,
            "injection_patterns": list(screening.patterns),
        },
        external_evidence=external_evidence,
        memory_traces=memory_traces,
        hypotheses=hypotheses,
        integration_status=integration_status,
        investigation_steps=steps,
        incomplete=incomplete,
        incomplete_reason="; ".join(incomplete_reasons) if incomplete_reasons else None,
    )
