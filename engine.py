from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from config import get_settings
from evidence.extractor import extract_claims
from evidence.graph import build_evidence_graph
from evidence.risk import calculate_risk
from agents.identity import run_identity
from agents.infrastructure import run_infrastructure
from agents.social_engineering import run_social_engineering
from agents.verifier import run_verifier
from models import (
    AnalysisResponse,
    InputType,
    RiskDecision,
)


async def analyze(
    content: str,
    input_type: InputType = "message",
    context: dict[str, Any] | None = None,
) -> AnalysisResponse:
    context = context or {}
    extraction = extract_claims(content)

    identity = await run_identity(extraction, context)
    infrastructure = await run_infrastructure(extraction, context)
    social = await run_social_engineering(extraction, content, context)

    combined = {
        "extraction": extraction.model_dump(mode="json"),
        "agents": {
            "identity": identity.model_dump(mode="json"),
            "infrastructure": infrastructure.model_dump(mode="json"),
            "social_engineering": social.model_dump(mode="json"),
        },
    }

    verification = await run_verifier(combined, context)
    score = calculate_risk(identity, infrastructure, social, verification)

    verdict = (
        "CRITICAL" if score >= 85 else
        "HIGH" if score >= 70 else
        "SUSPICIOUS" if score >= 45 else
        "LOW" if score >= 20 else
        "SAFE"
    )

    action = (
        "Do not click, respond, transfer money, or provide credentials. Verify through a trusted channel."
        if score >= 70 else
        "Pause and independently verify the sender, destination, and requested action."
        if score >= 45 else
        "Proceed only after normal security checks."
    )

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

    settings = get_settings()
    return AnalysisResponse(
        analysis_id=str(uuid4()),
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
        },
    )
