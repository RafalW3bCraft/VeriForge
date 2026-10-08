def calculate_risk(identity, infrastructure, social, verification):
    weighted = (
        0.25 * identity["score"]
        + 0.30 * infrastructure["score"]
        + 0.20 * social["score"]
        + 0.25 * verification["score"]
    )

    hard_signal = max(
        identity.get("critical_signal", 0),
        infrastructure.get("critical_signal", 0),
        social.get("critical_signal", 0),
    )
    return round(max(weighted, hard_signal), 1)
