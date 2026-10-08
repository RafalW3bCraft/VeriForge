import asyncio

from agents import verifier as verifier_module
from agents.verifier import run_verifier
from models import AgentResult, Evidence, ExtractionResult, Finding


def test_verifier_compares_findings_to_source_evidence(monkeypatch):
    monkeypatch.setattr(verifier_module, "demo_mode", lambda: True)
    extraction = ExtractionResult(
        evidence=[
            Evidence(id="domain-1", kind="domain", value="example.zip"),
            Evidence(id="credential-1", kind="credential_term", value="password"),
        ]
    )
    identity = AgentResult(score=28, confidence=0.8, summary="No identity evidence.")
    infrastructure = AgentResult(
        score=88,
        confidence=0.8,
        summary="URL structure.",
        findings=[Finding(
            finding="suspicious_destination_pattern",
            severity="high",
            evidence="example.zip",
            source="infrastructure_agent",
            confidence=0.8,
        )],
    )
    social = AgentResult(
        score=90,
        confidence=0.8,
        summary="Credential request.",
        findings=[Finding(
            finding="credential_request",
            severity="critical",
            evidence="password",
            source="social_engineering_agent",
            confidence=0.9,
        )],
    )
    combined = {
        "extraction": extraction.model_dump(mode="json"),
        "agents": {
            "identity": identity.model_dump(mode="json"),
            "infrastructure": infrastructure.model_dump(mode="json"),
            "social_engineering": social.model_dump(mode="json"),
        },
    }

    result = asyncio.run(run_verifier(combined, {}))

    assert result.evidence_strength == 1
    assert result.unsupported_claims == []
    assert "Identity evidence is inconclusive" in result.summary
    assert result.score == 100


def test_verifier_reports_unsupported_findings(monkeypatch):
    monkeypatch.setattr(verifier_module, "demo_mode", lambda: True)
    combined = {
        "extraction": {"evidence": []},
        "agents": {
            "identity": {
                "score": 70,
                "findings": [{
                    "finding": "sender_is_forged",
                    "severity": "high",
                    "evidence": "unverified external reputation",
                }],
            },
            "infrastructure": {"score": 20, "findings": []},
            "social_engineering": {"score": 20, "findings": []},
        },
    }

    result = asyncio.run(run_verifier(combined, {}))

    assert result.unsupported_claims == ["sender_is_forged"]
    assert result.missing_evidence
    assert result.score == 0