# VeriForge Build Plan — GenAI.Works Open Agent Hackathon 2026

Deadline: 2026-10-27 23:45 UTC (1.8 days remaining at audit time, 2026-10-26 05:00 UTC).

## Baseline audit results (verified by execution, not README)

| Component | State | Evidence |
| --- | --- | --- |
| Python test suite | PASS — 63/63 | `PYTHON_DOTENV_DISABLED=true python -m pytest -q` → `63 passed in 4.73s` |
| Frontend tests | PASS — 1/1 (minimal coverage) | `npm test` → `1 passed` |
| Frontend production build | PASS | `npm run build` → built in 2.58s |
| Offline benchmark (150 samples) | RUNS — binary F1 1.0, TN=45 of 50 benign | `python -m evaluation.runner` → `.artifacts/latest_report.md` |
| FastAPI app | Imports cleanly; health endpoints present | `apps/api/main.py` |
| Docker / Compose | Present, untested at audit time | `Dockerfile`, `docker-compose.yml` |

## Verified defects (addressed in new work)

1. `evidence/risk.py` — `calculate_risk` uses `max(weighted, hard_signal)`: an agent `critical_signal` overrides weighted risk with **no verification check**. A critical signal with zero supporting evidence can force CRITICAL verdict.
2. `agents/verifier.py` demo mode — evidence support decided by **substring match** (`value in finding["evidence"].casefold()`). Approximate, collision-prone.
3. `evaluation/metrics.py` — ambiguous observed labels are silently dropped from metrics; abstentions are neither counted nor reported. TN=45 of 50 benign in the report is a coverage artifact (5 benign predictions were normalized to "ambiguous" and filtered).
4. `apps/api/main.py` — `GET /api/analyses` and `GET /api/analyses/{id}` have **no authorization**; any caller can enumerate full analysis history.
5. `apps/api/main.py:191` — `detail=str(exc)` leaks internal exception text into API responses on the analyze path.
6. No evidence retention/sanitization policy on prompt re-injection; no prompt-injection screening of message content before it reaches the LLM context.
7. No external evidence retrieval: URL extraction is explicitly offline; nothing corroborates indicators against external data.
8. No persistent memory: each analysis is stateless; related messages investigated sequentially share nothing.
9. Frontend shows verdict/confidence but does not render evidence provenance, retrieval traces, or integration health.
10. `docs/architecture.md` does not describe Zetaris/Meterless (did not exist at baseline).

## Environment credential check (presence only, values never read)

- `ZETARIS_API_KEY`: present in `.env`
- `ZETARIS_URL` / `ZETARIS_BASE_URL`: ABSENT — live connectivity will need the instance URL from the user (blocker B1)
- `METERLESS_API_KEY`: present in `.env`
- `FEATHERLESS_API_KEY`: present
- H-MEM is a spec + TS reference implementation, not a hosted service: we will implement the contracts in-process (Python) following `AGENTS.md`, which the repo explicitly sanctions ("Implement it in TypeScript, Python, Rust, or whatever stack you ship. The contracts do not change.").

## Phases

- P0 AUDIT — done (this file + BASELINE_AND_NEW_WORK.md).
- P1 Zetaris integration: config layer, SQL-over-HTTP client (documented UI proxy route), template-validated read-only queries, threat-IOC datasets, typed evidence normalization, outage-aware status, unit tests (mocked) + live test gated on `ZETARIS_URL`.
- P2 Meterless H-MEM: Python implementation of canonical memory record, tiered store, hybrid retrieval with trace, trust ledger, conflict/supersede handling, per-investigation/per-tenant isolation, conformance-style tests.
- P3 Pipeline upgrade: hypotheses, bounded retrieval, evidence-linked explanation, inference labeling, risk gating on verification (fix D1/D2), step budget + failure handling.
- P4 Quality fixes: metrics coverage (D3), authorization on history (D4), error leakage (D5), prompt-injection screening + evidence sanitization (D6), architecture doc sync (D10).
- P5 Frontend: provenance panel, integration status, memory trace, failed/insufficient states.
- P6 Tests & security review; P7 docs & demo; P8 release verify.

## Cut list (drops first if time slips)

1. Frontend polish beyond provenance/memory panels.
2. H-MEM dreaming/sleep cycles (already out of critical path per brief).
3. Multi-dataset Zetaris ingestion beyond the minimum 2 sources for correlation.
4. NVIDIA enhancements (optional, unplanned).

## Blockers

- B1: `ZETARIS_URL` (instance base URL) absent from environment — live Zetaris acceptance gate needs it from the user. All other Zetaris work proceeds with mocked tests + a documented "unavailable" runtime path.
