from typing import Any

from agents.common import demo_mode, llm_json
from models import AgentResult, ExtractionResult, Finding


async def run_identity(
    extraction: ExtractionResult, context: dict[str, Any]
) -> AgentResult:
    if demo_mode():
        domains = extraction.domains
        mismatch = any(d and not d.endswith("github.com") for d in domains)
        findings: list[Finding] = []
        if mismatch:
            findings.append(Finding(
                finding="claimed_identity_not_supported_by_destination",
                severity="high",
                evidence=str(domains),
                source="identity_agent",
                confidence=0.86,
            ))
        return AgentResult(
            score=82 if mismatch else 28,
            critical_signal=92 if mismatch else 0,
            confidence=0.86,
            summary="Identity claim requires independent verification.",
            findings=findings,
        )

    return await llm_json(
        "Analyze sender identity and impersonation risk. Return JSON keys: "
        "score, critical_signal, confidence, summary, findings. "
        "Each finding must contain finding, severity, evidence, source, confidence.",
        {"extraction": extraction.model_dump(mode="json"), "context": context},
        AgentResult,
    )
