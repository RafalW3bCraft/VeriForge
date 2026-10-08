import pytest
from pydantic import ValidationError

from models import AnalysisRequest, AgentResult, Evidence, Finding, RiskDecision


def test_analysis_request_validates_size_and_input_type():
    request = AnalysisRequest(content="Check this message", input_type="email")

    assert request.input_type == "email"
    with pytest.raises(ValidationError):
        AnalysisRequest(content="", input_type="email")
    with pytest.raises(ValidationError):
        AnalysisRequest(content="message", input_type="unsupported")


def test_structured_outputs_reject_out_of_range_confidence_and_scores():
    with pytest.raises(ValidationError):
        Finding(
            finding="credential_request",
            severity="critical",
            evidence="password",
            source="social_engineering_agent",
            confidence=1.2,
        )
    with pytest.raises(ValidationError):
        AgentResult(score=101, confidence=0.8, summary="", findings=[])


def test_risk_decision_and_evidence_serialize_as_json():
    evidence = Evidence(id="url-1", kind="url", value="https://example.test")
    decision = RiskDecision(
        risk_score=10,
        confidence=0.8,
        evidence_strength=0.6,
        verdict="LOW",
        recommended_action="Verify through a trusted channel.",
    )

    assert evidence.model_dump(mode="json")["observed"] is True
    assert decision.model_dump(mode="json")["risk_score"] == 10