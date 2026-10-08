from evidence.extractor import extract_claims
from evidence.graph import build_evidence_graph
from models import AgentResult, Finding, RiskDecision


def test_graph_contains_observed_entities_and_grounded_findings():
    extraction = extract_claims(
        "URGENT: Sign in at https://github-security-check.zip and enter your password."
    )
    infrastructure = AgentResult(
        score=88,
        critical_signal=95,
        confidence=0.8,
        summary="Suspicious URL structure.",
        findings=[Finding(
            finding="suspicious_destination_pattern",
            severity="high",
            evidence="['github-security-check.zip']",
            source="infrastructure_agent",
            confidence=0.78,
        )],
    )
    social = AgentResult(
        score=70,
        critical_signal=90,
        confidence=0.9,
        summary="Credential request.",
        findings=[Finding(
            finding="credential_request",
            severity="critical",
            evidence="password",
            source="social_engineering_agent",
            confidence=0.96,
        )],
    )
    decision = RiskDecision(
        risk_score=92,
        confidence=0.9,
        evidence_strength=1,
        verdict="CRITICAL",
        recommended_action="Do not enter credentials.",
    )

    graph = build_evidence_graph(
        extraction,
        {"infrastructure": infrastructure, "social_engineering": social},
        decision,
    )

    node_types = {node.type for node in graph.nodes}
    assert {"url", "domain", "urgency_term", "credential_term", "finding", "decision"} <= node_types
    assert any(edge.relation == "supports" for edge in graph.edges)
    assert any(edge.relation == "contributes_to" for edge in graph.edges)
    assert not any(edge.relation == "workflow" for edge in graph.edges)


def test_graph_does_not_invent_evidence_nodes():
    extraction = extract_claims("Please review the attached notice.")
    decision = RiskDecision(
        risk_score=5,
        confidence=0.5,
        evidence_strength=0,
        verdict="SAFE",
        recommended_action="Verify the sender if unexpected.",
    )

    graph = build_evidence_graph(extraction, {}, decision)

    assert {node.type for node in graph.nodes} == {"input", "decision"}
    assert graph.edges == []