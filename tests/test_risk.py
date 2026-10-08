from evidence.risk import calculate_risk
from models import AgentResult, VerificationResult


def test_risk_score_is_deterministic_and_respects_hard_signal():
    identity = AgentResult(score=40, critical_signal=0, confidence=0.8, summary="")
    infrastructure = AgentResult(score=80, critical_signal=95, confidence=0.8, summary="")
    social = AgentResult(score=70, critical_signal=0, confidence=0.8, summary="")
    verification = VerificationResult(
        score=60, critical_signal=60, confidence=0.8, summary=""
    )

    result = calculate_risk(identity, infrastructure, social, verification)

    assert result == 95.0
    assert result == calculate_risk(identity, infrastructure, social, verification)


def test_risk_weights_can_be_overridden(monkeypatch):
    monkeypatch.setenv("RISK_WEIGHT_IDENTITY", "1")
    monkeypatch.setenv("RISK_WEIGHT_INFRASTRUCTURE", "0")
    monkeypatch.setenv("RISK_WEIGHT_SOCIAL", "0")
    monkeypatch.setenv("RISK_WEIGHT_VERIFICATION", "0")
    identity = AgentResult(score=35, confidence=0.8, summary="")
    others = AgentResult(score=90, confidence=0.8, summary="")
    verification = VerificationResult(score=90, confidence=0.8, summary="")

    assert calculate_risk(identity, others, others, verification) == 35