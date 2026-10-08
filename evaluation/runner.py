from __future__ import annotations

import asyncio
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from evaluation.dataset import EvaluationSample, build_default_dataset
from evaluation.metrics import (
    compute_agent_agreement,
    compute_binary_metrics,
    compute_evidence_coverage,
    compute_verification_consistency,
)
from evaluation.report import build_report, generate_markdown_report, save_report
from engine import analyze


def _expected_label(sample: EvaluationSample) -> str:
    if sample.category == "legitimate":
        return "benign"
    if sample.category in {"scam", "impersonation"}:
        return "malicious"
    return "ambiguous"


def _observed_label(verdict: str) -> str:
    normalized = str(verdict).upper()
    if normalized in {"HIGH", "CRITICAL"}:
        return "malicious"
    if normalized in {"SUSPICIOUS"}:
        return "ambiguous"
    return "benign"


def _agent_agreement_for(result: Any) -> float:
    agent_names = ["identity", "infrastructure", "social_engineering"]
    findings_by_agent = []
    for name in agent_names:
        agent = result.agents.model_dump().get(name, {})
        findings = agent.get("findings", [])
        if findings:
            findings_by_agent.append(tuple(f["finding"] for f in findings))
    return compute_agent_agreement(findings_by_agent)


def _verification_consistency_for(result: Any) -> float:
    verification = result.agents.model_dump().get("verification", {})
    unsupported = verification.get("unsupported_claims", [])
    return compute_verification_consistency(unsupported)


def _category_counts(dataset: list[EvaluationSample]) -> dict[str, int]:
    counts = Counter(sample.category for sample in dataset)
    return {
        "legitimate": counts.get("legitimate", 0),
        "scam": counts.get("scam", 0),
        "impersonation": counts.get("impersonation", 0),
        "ambiguous": counts.get("ambiguous", 0),
    }


async def _evaluate_sample(sample: EvaluationSample) -> dict[str, Any]:
    result = await analyze(sample.content, sample.input_type)
    observed_label = _observed_label(result.verdict)
    expected_label = _expected_label(sample)
    expected_features = list(sample.expected_evidence_characteristics)
    extracted_evidence = [item.value for item in result.extraction.evidence]
    evidence_coverage = compute_evidence_coverage(extracted_evidence, expected_features)

    agent_payload = result.agents.model_dump()
    return {
        "id": sample.id,
        "category": sample.category,
        "input_type": sample.input_type,
        "expected_verdict": sample.expected_verdict,
        "observed_verdict": result.verdict,
        "expected_label": expected_label,
        "observed_label": observed_label,
        "agent_agreement": _agent_agreement_for(result),
        "verification_consistency": _verification_consistency_for(result),
        "evidence_coverage": evidence_coverage,
        "extracted_evidence": extracted_evidence,
        "agent_findings": {
            name: [finding["finding"] for finding in payload.get("findings", [])]
            for name, payload in agent_payload.items()
        },
        "verification_result": {
            "summary": agent_payload["verification"]["summary"],
            "unsupported_claims": agent_payload["verification"]["unsupported_claims"],
            "evidence_strength": agent_payload["verification"]["evidence_strength"],
        },
        "deterministic_risk_result": {
            "risk_score": result.risk_decision.risk_score,
            "verdict": result.risk_decision.verdict,
            "confidence": result.risk_decision.confidence,
            "evidence_strength": result.risk_decision.evidence_strength,
        },
    }


def evaluate_dataset(dataset: list[EvaluationSample] | None = None) -> dict[str, Any]:
    active_dataset = list(dataset or build_default_dataset())
    os.environ["DEMO_MODE"] = "true"

    results = asyncio.run(_evaluate_all(active_dataset))

    expected_labels = [item["expected_label"] for item in results]
    observed_labels = [item["observed_label"] for item in results]
    metrics = compute_binary_metrics(expected_labels, observed_labels)

    category_performance: dict[str, Any] = {}
    for category in ["legitimate", "scam", "impersonation", "ambiguous"]:
        filtered = [item for item in results if item["category"] == category]
        paired_binary = [
            (item["expected_label"], item["observed_label"])
            for item in filtered
            if item["expected_label"] in {"benign", "malicious"}
            and item["observed_label"] in {"benign", "malicious"}
        ]
        category_expected = [expected for expected, _ in paired_binary]
        category_observed = [observed for _, observed in paired_binary]
        category_binary = compute_binary_metrics(category_expected, category_observed)
        category_performance[category] = {
            "count": len(filtered),
            "correct": sum(1 for item in filtered if item["expected_label"] == item["observed_label"]),
            "average_evidence_coverage": sum(item["evidence_coverage"] for item in filtered) / len(filtered) if filtered else 0.0,
            "metrics": category_binary,
        }

    confusion = {
        "tp": metrics["tp"],
        "fp": metrics["fp"],
        "tn": metrics["tn"],
        "fn": metrics["fn"],
        "total": len(results),
    }

    notable_failures = []
    for item in results:
        if item["expected_label"] == "malicious" and item["observed_label"] == "benign":
            notable_failures.append(f"Missed malicious sample {item['id']} ({item['category']})")
        if item["expected_label"] == "benign" and item["observed_label"] == "malicious":
            notable_failures.append(f"False positive on benign sample {item['id']} ({item['category']})")

    methodology = (
        "Deterministic benchmark using the real VeriForge analysis pipeline in demo mode, with a fixed offline dataset of 150 samples. "
        "Ambiguous cases are reported separately and excluded from the strict binary classification metrics."
    )

    report = build_report(
        dataset_size=len(active_dataset),
        category_counts=_category_counts(active_dataset),
        metrics={
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "f1": metrics["f1"],
            "false_positive_rate": metrics["false_positive_rate"],
            "false_negative_rate": metrics["false_negative_rate"],
            "agent_agreement": sum(item["agent_agreement"] for item in results) / len(results) if results else 0.0,
            "verification_consistency": sum(item["verification_consistency"] for item in results) / len(results) if results else 0.0,
            "evidence_coverage": sum(item["evidence_coverage"] for item in results) / len(results) if results else 0.0,
        },
        confusion_matrix=confusion,
        per_category=category_performance,
        notable_failures=notable_failures[:20],
        methodology=methodology,
    )
    report["samples"] = results
    return report


async def _evaluate_all(dataset: list[EvaluationSample]) -> list[dict[str, Any]]:
    samples = [await _evaluate_sample(sample) for sample in dataset]
    return samples


def main() -> None:
    dataset = build_default_dataset()
    report = evaluate_dataset(dataset)
    print(json.dumps({
        "dataset_total": report["dataset_total"],
        "metrics": report["metrics"],
        "confusion_matrix": report["confusion_matrix"],
        "category_counts": report["category_counts"],
    }, indent=2))
    output_path = Path(__file__).resolve().parent / "latest_report.json"
    save_report(report, output_path)
    markdown_path = Path(__file__).resolve().parent / "latest_report.md"
    markdown_path.write_text(generate_markdown_report(report), encoding="utf-8")


if __name__ == "__main__":
    main()
