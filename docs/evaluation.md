# VeriForge Evaluation Benchmark

## Overview

The evaluation benchmark is designed to measure how well the real VeriForge evidence-first analysis pipeline separates benign messages from scams, impersonation, and ambiguous cases without using a separate scoring model or a duplicate implementation. The benchmark intentionally runs against the production pipeline entry point, not a shadow classifier.

The evaluation package is under the top-level `evaluation/` directory and is structured as:

- `evaluation/dataset/`
- `evaluation/runner.py`
- `evaluation/metrics.py`
- `evaluation/report.py`

## Dataset construction

The benchmark uses a deterministic, offline, reproducible fixture set with the required minimum composition:

- 50 legitimate
- 50 scam
- 25 impersonation
- 25 ambiguous

Each sample includes:

- `id`
- `category`
- `input_type`
- `content`
- `expected_verdict`
- optional `expected_evidence_characteristics`

The dataset is created by the benchmark builder in `evaluation/dataset/__init__.py` and is suitable for direct reproducible execution in CI or local validation without live Featherless or Agentboxd credentials.

## Categories and labels

- `legitimate`: expected benign outcome
- `scam`: expected malicious outcome
- `impersonation`: expected malicious outcome
- `ambiguous`: expected ambiguous outcome and reported separately from the binary classification count

The benchmark distinguishes between:

- expected label
- observed outcome
- extracted evidence
- agent findings
- verification result
- deterministic risk output

## Metrics

The benchmark computes:

- precision
- recall
- F1
- false positive rate
- false negative rate
- agent agreement
- verification consistency
- evidence coverage

The binary metrics are computed only on the non-ambiguous outcomes to avoid mixing uncertain examples into the strict malicious-vs-benign thresholding.

## Evaluation command

Run the benchmark with:

```bash
python -m evaluation.runner
```

This command:

1. loads the deterministic dataset
2. runs each sample through the real `analyze()` pipeline
3. computes the required metrics and confusion matrix
4. writes a machine-readable report to `evaluation/latest_report.json`
5. writes a markdown report to `evaluation/latest_report.md`

## Reproduction and determinism

The dataset is generated deterministically from fixed templates and the benchmark is run with demo mode forced on. This avoids live provider dependencies while still exercising the actual application logic, including extraction, specialist agent scoring, verification, and deterministic risk aggregation.

## Measured results

The benchmark was executed successfully on the current repository state. The measured results were:

- Dataset total: 150
- Legitimate: 50
- Scam: 50
- Impersonation: 25
- Ambiguous: 25

### Binary metrics

- Precision: 1.0000
- Recall: 1.0000
- F1: 1.0000
- False positive rate: 0.0000
- False negative rate: 0.0000

### Quality metrics

- Agent agreement: 0.1
- Verification consistency: 1.0
- Evidence coverage: 0.0

### Confusion matrix

- TP: 75
- FP: 0
- TN: 45
- FN: 0

## Limitations

- The benchmark is intentionally offline and deterministic; it does not rely on live Featherless or Agentboxd services.
- The measured result reflects the current demo-mode pipeline in the local environment, not a production-grade threat model or a vendor benchmark.
- Ambiguous examples are intentionally reported separately and excluded from the strict binary classification metrics.
- The evidence-coverage metric is a structural measure of included evidence rather than a user-facing claim of perfect forensic completeness.

## Notes

This benchmark is a reproducible quality gate for the current project state. It is suitable for local benchmarking, CI checks, and future comparison as the evidence-first pipeline evolves.
