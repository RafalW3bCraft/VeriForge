from config import get_settings
from models import AgentResult, VerificationResult

# A critical signal may only lift the final score above the weighted value
# when verification actually supports the underlying findings. Otherwise an
# unverified agent claim could force a CRITICAL verdict (baseline defect).
MIN_VERIFICATION_SUPPORT_FOR_HARD_SIGNAL = 0.34


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
    verification_supports = verification.evidence_strength >= MIN_VERIFICATION_SUPPORT_FOR_HARD_SIGNAL
    if hard_signal > weighted and verification_supports:
        return round(hard_signal, 1)
    return round(weighted, 1)
