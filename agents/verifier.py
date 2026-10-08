from typing import Any

from agents.common import demo_mode, llm_json
from models import VerificationResult


async def run_verifier(
    combined: dict[str, Any], context: dict[str, Any]
) -> VerificationResult:
    if demo_mode():
        agents = combined["agents"]
        scores = [a["score"] for a in agents.values()]
        spread = max(scores) - min(scores)
        evidence_values = [
            evidence["value"].casefold()
            for evidence in combined["extraction"]["evidence"]
        ]
        findings = [
            (agent_name, finding)
            for agent_name, result in agents.items()
            for finding in result["findings"]
        ]
        supported = [
            (agent_name, finding)
            for agent_name, finding in findings
            if any(value in finding["evidence"].casefold() for value in evidence_values)
        ]
        unsupported = [
            finding["finding"]
            for agent_name, finding in findings
            if (agent_name, finding) not in supported
        ]
        supported_sources = {agent_name for agent_name, _ in supported}
        severity_scores = {"low": 25, "medium": 55, "high": 80, "critical": 95}
        score = max(
            (severity_scores[finding["severity"]] for _, finding in supported),
            default=0,
        )
        if len(supported_sources) > 1:
            score = min(100, score + 5 * (len(supported_sources) - 1))
        evidence_strength = len(supported) / len(findings) if findings else 0.0
        agreements = [
            f"{value} is cited by multiple specialist agents"
            for value in dict.fromkeys(evidence_values)
            if len({
                agent_name for agent_name, finding in supported
                if value in finding["evidence"].casefold()
            }) > 1
        ]
        disagreements = (
            [f"Specialist risk scores differ by {spread} points"]
            if spread >= 45 else []
        )
        missing_evidence = [
            f"No extracted source evidence supports {finding_name}"
            for finding_name in unsupported
        ]
        if not agents["identity"]["findings"] and {
            "infrastructure", "social_engineering"
        } <= supported_sources:
            summary = (
                "Identity evidence is inconclusive, while infrastructure and "
                "behavioral evidence strongly indicate risk."
            )
        elif not supported:
            summary = "Insufficient evidence supports the specialist risk findings."
        else:
            summary = (
                f"{len(supported)} specialist finding(s) are traceable to extracted "
                "source evidence."
            )
        return VerificationResult(
            score=score,
            critical_signal=0,
            confidence=evidence_strength,
            summary=summary,
            findings=[],
            agreements=agreements,
            disagreements=disagreements,
            missing_evidence=missing_evidence,
            unsupported_claims=unsupported,
            evidence_strength=evidence_strength,
        )

    return await llm_json(
        "Act as the final evidence verifier. Check agreement, contradiction, "
        "missing support, unsupported claims, and evidence quality. You receive "
        "source evidence snippets and specialist findings; do not rely only on "
        "agent summaries. Cite only supplied evidence. If a finding is unsupported, "
        "say so. Return score, critical_signal, confidence, summary, findings, "
        "agreements, disagreements, contradictions, missing_evidence, "
        "unsupported_claims, evidence_strength. Do not set the final risk score.",
        combined | {"context": context},
        VerificationResult,
    )
