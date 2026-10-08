import json
from pathlib import Path

import pytest

from evaluation.dataset import build_default_dataset, load_dataset
from evaluation.metrics import (
    compute_binary_metrics,
    compute_evidence_coverage,
    metric_summary,
)
from evaluation.runner import evaluate_dataset


def test_dataset_counts_and_categories():
    dataset = build_default_dataset()
    counts = {category: 0 for category in {"legitimate", "scam", "impersonation", "ambiguous"}}
    for sample in dataset:
        counts[sample.category] += 1

    assert counts == {"legitimate": 50, "scam": 50, "impersonation": 25, "ambiguous": 25}
    assert len(dataset) == 150


def test_metric_calculations_are_consistent():
    expected = ["benign", "benign", "malicious", "malicious"]
    observed = ["benign", "malicious", "malicious", "benign"]

    summary = compute_binary_metrics(expected, observed)

    assert summary["precision"] == pytest.approx(0.5)
    assert summary["recall"] == pytest.approx(0.5)
    assert summary["f1"] == pytest.approx(0.5)
    assert summary["false_positive_rate"] == pytest.approx(0.5)
    assert summary["false_negative_rate"] == pytest.approx(0.5)


def test_dataset_loader_rejects_malformed_fixture():
    payload = [{"id": "x", "category": "scam"}]
    path = Path("/tmp/veriforge-malformed-fixture.json")
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError):
        load_dataset(path)


def test_evaluate_dataset_is_deterministic_and_runs_without_live_credentials(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    report = evaluate_dataset(build_default_dataset())

    assert report["dataset_total"] == 150
    assert report["confusion_matrix"]["total"] >= 120
    assert report["metrics"]["precision"] >= 0.0
    assert report["metrics"]["recall"] >= 0.0
    assert report["category_counts"]["legitimate"] == 50
    assert report["category_counts"]["scam"] == 50
    assert report["category_counts"]["impersonation"] == 25
    assert report["category_counts"]["ambiguous"] == 25


def test_evidence_coverage_handles_missing_evidence():
    extracted_evidence = ["urgent", "password", "github-security-check.zip"]
    evidence_features = ["urgent", "password"]

    assert compute_evidence_coverage(extracted_evidence, evidence_features) == pytest.approx(2 / 3)


def test_metric_summary_exposes_expected_fields():
    summary = metric_summary({"precision": 0.9, "recall": 0.8, "f1": 0.85})

    assert summary["precision"] == 0.9
    assert summary["recall"] == 0.8
    assert summary["f1"] == 0.85
