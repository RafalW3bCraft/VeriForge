"""Evaluation tooling for VeriForge."""

from .dataset import EvaluationSample, build_default_dataset, load_dataset
from .metrics import (
    compute_agent_agreement,
    compute_binary_metrics,
    compute_evidence_coverage,
    compute_verification_consistency,
    metric_summary,
)
from .report import build_report, generate_markdown_report

__all__ = [
    "EvaluationSample",
    "build_default_dataset",
    "load_dataset",
    "compute_binary_metrics",
    "compute_agent_agreement",
    "compute_verification_consistency",
    "compute_evidence_coverage",
    "metric_summary",
    "build_report",
    "generate_markdown_report",
]
