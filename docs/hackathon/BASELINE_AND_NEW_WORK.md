# Baseline vs New Work

Baseline commit: `ff32c6cdd5e7762844dda3e80ac8f96e63db681b` ("feat: finalized the frame-blueprint, ready for submission", 2026-10-10).
Nothing at or before that commit is claimed as hackathon work.

## Pre-existing components (baseline, NOT new work)

- `engine.py` — investigation pipeline orchestrator (extract → 3 specialist agents → verifier → risk → graph → persist).
- `models.py` — pydantic contracts (AnalysisRequest/Response, Claim, Evidence, Finding, AgentResult, VerificationResult, RiskDecision, EvidenceGraph).
- `config.py` — env-driven settings, risk weights validation.
- `database.py` — SQLAlchemy SQLite persistence, retention, analysis history.
- `apps/api/main.py` — FastAPI app, rate limiting, webhook endpoint, static frontend serving.
- `agents/` — identity, infrastructure, social_engineering, verifier specialists (demo-mode heuristics + Featherless LLM path).
- `evidence/` — extractor (URLs/domains/emails/urgency/credential/financial heuristics), graph builder, deterministic risk.
- `integrations/featherless.py` — LLM provider client. `integrations/agentboxd.py` — signed webhook ingestion.
- `evaluation/` — 150-sample offline dataset, runner, metrics, report.
- `frontend/` — React 19 + Vite 6 + Tailwind 4 UI (analyze form, verdict, findings, history).
- `tests/` — 63 passing tests. Dockerfile, docker-compose.yml, GitHub workflow.
- Docs: architecture, threat-model, evaluation, FEATHERLESS, AGENTBOXD, submission-checklist.

## New components (implemented after baseline — hackathon work)

To be filled as implementation lands. Planned:

- `integrations/zetaris/` — Zetaris client, config, query templates, IOC normalization. NEW.
- `hmem/` — H-MEM memory engine (store, retrieval, trust ledger, conflicts) per Meterless spec. NEW.
- Pipeline v2 in `engine.py` — hypotheses, evidence correlation, memory context, bounded re-retrieval, gated risk. MODIFIED.
- API auth on history endpoints; error-message sanitization. MODIFIED.
- Frontend provenance/memory/status panels. MODIFIED.
- `docs/hackathon/*` — all submission artifacts. NEW.

## Change report

Final machine-generated diff summary to be produced at release: `git diff ff32c6c..HEAD --stat` appended here and to NEW_WORK_CHANGELOG.md.
