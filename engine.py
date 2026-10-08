import os
from evidence.extractor import extract_claims
from evidence.risk import calculate_risk
from agents.identity import run_identity
from agents.infrastructure import run_infrastructure
from agents.social_engineering import run_social_engineering
from agents.verifier import run_verifier

async def analyze(content: str, input_type: str = "message", context: dict | None = None):
    context = context or {}
    extraction = extract_claims(content)

    identity = await run_identity(extraction, context)
    infrastructure = await run_infrastructure(extraction, context)
    social = await run_social_engineering(extraction, content, context)

    combined = {
        "extraction": extraction,
        "agents": {
            "identity": identity,
            "infrastructure": infrastructure,
            "social_engineering": social,
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
        identity["findings"]
        + infrastructure["findings"]
        + social["findings"]
        + verification["findings"]
    )

    graph = {
        "nodes": [
            {"id": "input", "label": "Input", "type": "input"},
            {"id": "identity", "label": "Identity Agent", "type": "agent"},
            {"id": "infra", "label": "Infrastructure Agent", "type": "agent"},
            {"id": "social", "label": "Social Engineering Agent", "type": "agent"},
            {"id": "verifier", "label": "Verification Agent", "type": "agent"},
            {"id": "decision", "label": "Risk Decision", "type": "decision"},
        ],
        "edges": [
            {"source": "input", "target": "identity"},
            {"source": "input", "target": "infra"},
            {"source": "input", "target": "social"},
            {"source": "identity", "target": "verifier"},
            {"source": "infra", "target": "verifier"},
            {"source": "social", "target": "verifier"},
            {"source": "verifier", "target": "decision"},
        ],
    }

    return {
        "input_type": input_type,
        "score": score,
        "verdict": verdict,
        "confidence": verification["confidence"],
        "summary": verification["summary"],
        "recommended_action": action,
        "extraction": extraction,
        "findings": findings,
        "agents": {
            "identity": identity,
            "infrastructure": infrastructure,
            "social_engineering": social,
            "verification": verification,
        },
        "graph": graph,
        "meta": {
            "mode": "demo" if os.getenv("DEMO_MODE", "true").lower() == "true" else "featherless",
            "principle": "LLM reasoning operates on evidence; risk is computed separately."
        },
    }
