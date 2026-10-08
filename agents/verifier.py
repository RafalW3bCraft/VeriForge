from agents.common import demo_mode, llm_json

async def run_verifier(combined, context):
    if demo_mode():
        agents = combined["agents"]
        scores = [a["score"] for a in agents.values()]
        spread = max(scores) - min(scores)
        evidence_count = sum(len(a["findings"]) for a in agents.values())
        score = min(100, 50 + evidence_count * 8)
        if spread > 45:
            score = max(40, score - 10)
        return {
            "score": score,
            "critical_signal": score,
            "confidence": min(0.97, 0.70 + evidence_count * 0.05),
            "summary": "Independent findings were correlated and checked for agreement or conflict.",
            "findings": [{
                "finding": "multi_agent_evidence_correlation",
                "severity": "high" if evidence_count >= 2 else "medium",
                "evidence": f"{evidence_count} findings; score spread={spread}",
                "source": "verification_agent",
                "confidence": 0.90
            }]
        }

    return await llm_json(
        "Act as the final evidence verifier. Check agreement, contradiction, "
        "missing support, and unsupported claims. Do not add outside facts. "
        "Return score, critical_signal, confidence, summary, findings.",
        combined | {"context": context},
    )
