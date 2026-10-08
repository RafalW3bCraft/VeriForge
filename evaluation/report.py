from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_report(dataset_size: int, category_counts: dict[str, int], metrics: dict[str, Any], confusion_matrix: dict[str, int], per_category: dict[str, Any], notable_failures: list[str], methodology: str) -> dict[str, Any]:
    return {
        "dataset_total": dataset_size,
        "category_counts": category_counts,
        "metrics": metrics,
        "confusion_matrix": confusion_matrix,
        "per_category": per_category,
        "notable_failures": notable_failures,
        "methodology": methodology,
        "limitations": [
            "This benchmark is deterministic and offline; it does not rely on live Featherless or Agentboxd services.",
            "The result reflects the current demo-mode heuristic pipeline used in the local evaluation environment.",
            "Ambiguous examples are reported separately and are excluded from the strict binary classification count.",
        ],
    }


def generate_markdown_report(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    lines = [
        "# VeriForge Evaluation Report",
        "",
        f"- Dataset total: {report['dataset_total']}",
        f"- Legitimate: {report['category_counts'].get('legitimate', 0)}",
        f"- Scam: {report['category_counts'].get('scam', 0)}",
        f"- Impersonation: {report['category_counts'].get('impersonation', 0)}",
        f"- Ambiguous: {report['category_counts'].get('ambiguous', 0)}",
        "",
        "## Methodology",
        report["methodology"],
        "",
        "## Binary metrics",
        f"- Precision: {metrics.get('precision', 0.0):.4f}",
        f"- Recall: {metrics.get('recall', 0.0):.4f}",
        f"- F1: {metrics.get('f1', 0.0):.4f}",
        f"- False positive rate: {metrics.get('false_positive_rate', 0.0):.4f}",
        f"- False negative rate: {metrics.get('false_negative_rate', 0.0):.4f}",
        "",
        "## Confusion matrix",
        f"- TP: {report['confusion_matrix'].get('tp', 0)}",
        f"- FP: {report['confusion_matrix'].get('fp', 0)}",
        f"- TN: {report['confusion_matrix'].get('tn', 0)}",
        f"- FN: {report['confusion_matrix'].get('fn', 0)}",
        "",
        "## Notable failures",
    ]
    if report["notable_failures"]:
        for failure in report["notable_failures"]:
            lines.append(f"- {failure}")
    else:
        lines.append("- No notable failures recorded.")

    return "\n".join(lines) + "\n"


def save_report(report: dict[str, Any], output_path: str | Path) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return target
