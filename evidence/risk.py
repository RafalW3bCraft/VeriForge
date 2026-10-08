from config import get_settings
from models import AgentResult, VerificationResult


def calculate_risk(
    identity: AgentResult,
    infrastructure: AgentResult,
    social: AgentResult,
    verification: VerificationResult,
) -> float:
    weights = get_settings().risk_weights
    weighted = sum(
        weight * result.score
        for weight, result in zip(
            weights, (identity, infrastructure, social, verification), strict=True
        )
    )

    hard_signal = max(
        identity.critical_signal,
        infrastructure.critical_signal,
        social.critical_signal,
    )
    return round(max(weighted, hard_signal), 1)
