from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def _normalize_label(value: str | None) -> str:
    if value is None:
        return "unknown"
    normalized = str(value).strip().casefold()
    if normalized in {"high", "critical", "malicious", "fraud", "phish"}:
        return "malicious"
    if normalized in {"safe", "low", "benign", "ok", "good"}:
        return "benign"
    if normalized in {"suspicious", "ambiguous", "warning"}:
        return "ambiguous"
    return normalized


def compute_binary_metrics(expected: Sequence[str], observed: Sequence[str]) -> dict[str, float]:
    if len(expected) != len(observed):
        raise ValueError("Expected and observed label lists must have the same length")

    pairings = [
        (_normalize_label(expected_value), _normalize_label(observed_value))
        for expected_value, observed_value in zip(expected, observed, strict=True)
    ]
    filtered = [
        (expected_label, observed_label)
        for expected_label, observed_label in pairings
        if expected_label in {"benign", "malicious"}
        and observed_label in {"benign", "malicious"}
    ]

    if not filtered:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "false_positive_rate": 0.0,
            "false_negative_rate": 0.0,
            "tp": 0,
            "fp": 0,
            "tn": 0,
            "fn": 0,
        }

    tp = sum(1 for expected_label, observed_label in filtered if expected_label == "malicious" and observed_label == "malicious")
    fp = sum(1 for expected_label, observed_label in filtered if expected_label == "benign" and observed_label == "malicious")
    tn = sum(1 for expected_label, observed_label in filtered if expected_label == "benign" and observed_label == "benign")
    fn = sum(1 for expected_label, observed_label in filtered if expected_label == "malicious" and observed_label == "benign")

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    false_positive_rate = fp / (fp + tn) if (fp + tn) else 0.0
    false_negative_rate = fn / (fn + tp) if (fn + tp) else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positive_rate": false_positive_rate,
        "false_negative_rate": false_negative_rate,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
    }


def compute_agent_agreement(agent_results: Sequence[tuple[str, ...]] | Sequence[Sequence[str]]) -> float:
    if not agent_results:
        return 0.0

    agreements = 0
    total = 0
    for result in agent_results:
        unique = {str(item).strip().lower() for item in result if str(item).strip()}
        if len(unique) >= 2:
            total += 1
            agreements += 1
        elif unique:
            total += 1
    return agreements / total if total else 0.0


def compute_verification_consistency(unsupported_claims: Sequence[str] | int = ()) -> float:
    if isinstance(unsupported_claims, int):
        return 1.0 if unsupported_claims == 0 else 0.0
    return 1.0 if not unsupported_claims else 0.0


def compute_evidence_coverage(extracted_evidence: Sequence[str], expected_features: Sequence[str]) -> float:
    if not expected_features:
        return 1.0

    extracted_norm = {str(item).strip().lower() for item in extracted_evidence if str(item).strip()}
    expected_norm = {str(item).strip().lower() for item in expected_features if str(item).strip()}
    if not expected_norm:
        return 1.0
    if not extracted_norm:
        return 0.0

    coverage = len(extracted_norm & expected_norm) / len(extracted_norm)
    return max(0.0, min(1.0, coverage))


def metric_summary(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        key: metrics.get(key, 0.0)
        for key in [
            "precision",
            "recall",
            "f1",
            "false_positive_rate",
            "false_negative_rate",
            "tp",
            "fp",
            "tn",
            "fn",
        ]
    }
