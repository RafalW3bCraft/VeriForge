# Pre-existing Work Disclosure

Baseline commit: **ff32c6cdd5e7762844dda3e80ac8f96e63db681b**
("feat: finalized the frame-blueprint, ready for submission", 2026-10-10).

Everything at or before that commit predates this hackathon submission and is
NOT claimed as new hackathon work. Git history is preserved; the full
baseline-to-head diff is available via `git diff ff32c6c..HEAD`.

## Pre-existing at baseline (not new work)

- FastAPI backend with rate limiting, security headers, signed Agentboxd
  webhook ingestion, SQLite persistence, retention.
- Deterministic investigation pipeline: extraction → identity /
  infrastructure / social-engineering specialist agents → verifier → risk →
  evidence graph → persist.
- Demo-mode heuristics and Featherless LLM integration.
- React/Vite frontend (analyze form, verdict view, graph view, history).
- Offline evaluation harness with a 150-sample dataset.
- Dockerfile, docker-compose.yml, GitHub Actions workflow.
- Documentation set under `docs/`.
- 63 passing Python tests; 1 passing frontend test.

## Known baseline defects (fixed as new work, documented in NEW_WORK_CHANGELOG)

1. `calculate_risk`: hard critical signal overruled weighted risk with no
   verification check.
2. Demo-mode verifier: evidence support by substring matching (collision-prone).
3. Benchmark: ambiguous predictions silently dropped from metrics (coverage
   artifact; baseline report showed TN=45 of 50 benign).
4. Analysis history endpoints had no authorization.
5. Analyze endpoint leaked internal exception text in 500 responses.
6. No external evidence retrieval; no persistent memory; no prompt-injection
   screening; no evidence provenance in the UI.

## Tool usage

- Cursor: not used for this submission.
- AI assistance: Hermes Agent (Nous Research, Kimi-K3 model) performed the
  implementation under human direction; the submitter directed scope,
  reviewed the audit, and owns all decisions.
