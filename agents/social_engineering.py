from agents.common import demo_mode, llm_json

async def run_social_engineering(extraction, content, context):
    if demo_mode():
        urgency = len(extraction.get("urgency_terms", []))
        creds = extraction.get("requests_credentials")
        money = extraction.get("requests_financial_action")
        score = min(100, 20 + 20 * urgency + (30 if creds else 0) + (25 if money else 0))
        findings = []
        if urgency:
            findings.append({
                "finding": "urgency_manipulation",
                "severity": "high" if urgency >= 2 else "medium",
                "evidence": ", ".join(extraction["urgency_terms"]),
                "source": "social_engineering_agent",
                "confidence": 0.91
            })
        if creds:
            findings.append({
                "finding": "credential_request",
                "severity": "critical",
                "evidence": ", ".join(extraction["credential_terms"]),
                "source": "social_engineering_agent",
                "confidence": 0.96
            })
        if money:
            findings.append({
                "finding": "financial_action_request",
                "severity": "critical",
                "evidence": ", ".join(extraction["financial_terms"]),
                "source": "social_engineering_agent",
                "confidence": 0.94
            })
        return {
            "score": score,
            "critical_signal": 97 if creds and money else (90 if creds or money else 0),
            "confidence": 0.92,
            "summary": "Behavioral manipulation signals detected from the message itself.",
            "findings": findings
        }

    return await llm_json(
        "Analyze social-engineering tactics: urgency, authority pressure, secrecy, "
        "credential requests, payment requests, fear, and unusual instructions. "
        "Return score, critical_signal, confidence, summary, findings.",
        {"message": content, "extraction": extraction, "context": context},
    )
