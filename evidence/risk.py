from config import get_settings
from models import AgentResult, VerificationResult

# A critical signal may only lift the final score above the weighted value
# when verification actually supports the underlying findings. Otherwise an
# unverified agent claim could force a CRITICAL verdict (baseline defect).
MIN_VERIFICATION_SUPPORT_FOR_HARD_SIGNAL = 0.34


def _verified_support(verification: VerificationResult) -> float:
    """Return the proportion of the decision supported by traceable evidence.

    Specialist scores are model output and therefore never authoritative by
    themselves. Evidence strength is produced by the verifier from source
    evidence; unsupported findings cannot increase the final decision.
    """
    supported = [
        finding
        for finding in verification.findings
        if finding.evidence_ids and finding.finding not in verification.unsupported_claims
    ]
    if verification.findings and not supported:
        return 0.0
    return verification.evidence_strength


def calculate_risk(
    identity: AgentResult,
    infrastructure: AgentResult,
    social: AgentResult,
    verification: VerificationResult,
) -> float:
    weights = get_settings().risk_weights
    support = _verified_support(verification)
    # Every score, including the verifier score, is damped by evidence support.
    # This intentionally favours an uncertain result over an authoritative
    # verdict when the available evidence is incomplete or contradictory.
    weighted = sum(
        weight * result.score * support
        for weight, result in zip(
            weights, (identity, infrastructure, social, verification), strict=True
        )
    )

    hard_signal = max(
        identity.critical_signal,
        infrastructure.critical_signal,
        social.critical_signal,
    )
    verification_supports = support >= MIN_VERIFICATION_SUPPORT_FOR_HARD_SIGNAL
    if hard_signal > weighted and verification_supports:
        return round(hard_signal, 1)
    return round(weighted, 1)
