from agents.common import demo_mode, llm_json

async def run_identity(extraction, context):
    if demo_mode():
        domains = extraction.get("domains", [])
        mismatch = any(d and not d.endswith("github.com") for d in domains)
        findings = []
        if mismatch:
            findings.append({
                "finding": "claimed_identity_not_supported_by_destination",
                "severity": "high",
                "evidence": str(domains),
                "source": "identity_agent",
                "confidence": 0.86
            })
        return {
            "score": 82 if mismatch else 28,
            "critical_signal": 92 if mismatch else 0,
            "confidence": 0.86,
            "summary": "Identity claim requires independent verification.",
            "findings": findings
        }

    return await llm_json(
        "Analyze sender identity and impersonation risk. Return JSON keys: "
        "score, critical_signal, confidence, summary, findings. "
        "Each finding must contain finding, severity, evidence, source, confidence.",
        {"extraction": extraction, "context": context},
    )
