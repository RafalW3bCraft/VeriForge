from typing import Any

from agents.common import demo_mode, llm_json
from models import AgentResult, ExtractionResult, Finding


async def run_identity(
    extraction: ExtractionResult, context: dict[str, Any]
) -> AgentResult:
    if demo_mode():
        domains = extraction.domains
        claimed_brand = str(context.get("claimed_brand") or context.get("brand") or "").strip().casefold()
        sender = str(context.get("sender") or context.get("from") or "").strip().casefold()
        sender_domain = context.get("sender_domain") or context.get("source_domain")
        if sender_domain:
            sender_domain = str(sender_domain).strip().casefold()
        findings: list[Finding] = []
        mismatch = False
        identity_evidence = bool(claimed_brand or sender or sender_domain)

        if identity_evidence and domains:
            for domain in domains:
                lowered = domain.casefold()
                if claimed_brand and claimed_brand not in lowered:
                    mismatch = True
                    findings.append(Finding(
                        finding="identity_claim_does_not_match_destination_domain",
                        severity="high",
                        evidence=f"claimed_brand={claimed_brand}; destination={domain}",
                        source="identity_agent",
                        confidence=0.84,
                    ))
                    break
                if sender_domain and sender_domain not in lowered:
                    mismatch = True
                    findings.append(Finding(
                        finding="sender_context_does_not_match_destination_domain",
                        severity="medium",
                        evidence=f"sender_domain={sender_domain}; destination={domain}",
                        source="identity_agent",
                        confidence=0.8,
                    ))
                    break

        if not identity_evidence:
            return AgentResult(
                score=12,
                critical_signal=0,
                confidence=0.5,
                summary="Identity evidence is inconclusive without a claimed brand, sender identity, or domain context.",
                findings=[],
            )

        if mismatch:
            return AgentResult(
                score=68,
                critical_signal=72,
                confidence=0.82,
                summary="Identity evidence suggests a mismatch between the claimed sender context and the destination or supplied domain.",
                findings=findings,
            )

        return AgentResult(
            score=22,
            critical_signal=0,
            confidence=0.7,
            summary="The supplied identity context is consistent with the observed evidence.",
            findings=[],
        )

    return await llm_json(
        "Analyze sender identity and impersonation risk. Return JSON keys: "
        "score, critical_signal, confidence, summary, findings. "
        "Each finding must contain finding, severity, evidence, source, confidence.",
        {"extraction": extraction.model_dump(mode="json"), "context": context},
        AgentResult,
    )
