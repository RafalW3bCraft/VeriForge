from agents.common import demo_mode, llm_json

SUSPICIOUS_TLDS = {".zip", ".mov", ".click", ".top", ".xyz"}

async def run_infrastructure(extraction, context):
    if demo_mode():
        domains = extraction.get("domains", [])
        suspicious = any(any(d.endswith(t) for t in SUSPICIOUS_TLDS) for d in domains)
        findings = []
        if suspicious:
            findings.append({
                "finding": "suspicious_destination_pattern",
                "severity": "high",
                "evidence": str(domains),
                "source": "infrastructure_agent",
                "confidence": 0.78
            })
        elif domains:
            findings.append({
                "finding": "destination_present",
                "severity": "medium",
                "evidence": str(domains),
                "source": "infrastructure_agent",
                "confidence": 0.92
            })
        return {
            "score": 88 if suspicious else (55 if domains else 12),
            "critical_signal": 95 if suspicious else 0,
            "confidence": 0.83,
            "summary": "Infrastructure evidence is based on observable URL/domain structure.",
            "findings": findings
        }

    return await llm_json(
        "Analyze only supplied URL/domain/infrastructure evidence. Do not claim "
        "reputation, DNS, registration, certificate, redirect, or blacklist facts "
        "unless supplied. Return score, critical_signal, confidence, summary, findings.",
        {"extraction": extraction, "context": context},
    )
