from typing import Any

from agents.common import demo_mode, llm_json
from models import AgentResult, ExtractionResult, Finding


async def run_social_engineering(
    extraction: ExtractionResult, content: str, context: dict[str, Any]
) -> AgentResult:
    if demo_mode():
        urgency = len(extraction.urgency_terms)
        creds = extraction.requests_credentials
        money = extraction.requests_financial_action
        score = min(100, 20 + 20 * urgency + (30 if creds else 0) + (25 if money else 0))
        findings: list[Finding] = []
        if urgency:
            findings.append(Finding(
                finding="urgency_manipulation",
                severity="high" if urgency >= 2 else "medium",
                evidence=", ".join(extraction.urgency_terms),
                source="social_engineering_agent",
                confidence=0.91,
            ))
        if creds:
            findings.append(Finding(
                finding="credential_request",
                severity="critical",
                evidence=", ".join(extraction.credential_terms),
                source="social_engineering_agent",
                confidence=0.96,
            ))
        if money:
            findings.append(Finding(
                finding="financial_action_request",
                severity="critical",
                evidence=", ".join(extraction.financial_terms),
                source="social_engineering_agent",
                confidence=0.94,
            ))
        return AgentResult(
            score=score,
            critical_signal=97 if creds and money else (90 if creds or money else 0),
            confidence=0.92,
            summary="Behavioral manipulation signals detected from the message itself.",
            findings=findings,
        )

    return await llm_json(
        "Analyze social-engineering tactics: urgency, authority pressure, secrecy, "
        "credential requests, payment requests, fear, and unusual instructions. "
        "Return score, critical_signal, confidence, summary, findings.",
        {
            "message": content,
            "extraction": extraction.model_dump(mode="json"),
            "context": context,
        },
        AgentResult,
    )
