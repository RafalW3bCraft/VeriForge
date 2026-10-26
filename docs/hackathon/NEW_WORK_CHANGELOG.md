# New Work Changelog (baseline ff32c6c → HEAD 04e83bb)

Diff summary: **34 files changed, 3115 insertions(+), 21 deletions(-)** in one
commit (`04e83bb`). `git diff ff32c6c..HEAD --stat` for the full list.

## New files

- `integrations/zetaris/` — Zetaris client package (client.py, __init__.py).
- `hmem/` — H-MEM engine (models, store, retrieval, ledger, conflicts, engine).
- `evidence/external.py` — Zetaris correlation and evidence normalization.
- `evidence/sanitize.py` — prompt-injection screening, snippet sanitization.
- `tests/test_zetaris.py` (161 lines) — SQL validation, template rendering,
  auth headers, error statuses, injection rejection, env-gated live test.
- `tests/test_hmem.py` (288 lines) — 23 conformance-style contract tests.
- `tests/test_pipeline_v2.py` (123 lines) — injection screening, Zetaris
  outage behavior, cross-investigation memory acceptance gate, tenant isolation.
- `tests/test_api_security.py` — history authorization, error sanitization,
  truthful integrations status.
- `docs/hackathon/` — all submission artifacts (this directory).

## Modified files

- `engine.py` — pipeline v2: screening, hypotheses, external evidence, memory
  context, bounded re-retrieval, integration status, incomplete reporting,
  memory persistence, verdict capping on incomplete investigations.
- `models.py` — Finding.evidence_ids / is_inference; ExternalEvidence,
  MemoryTrace, IntegrationStatus, Hypothesis; AnalysisResponse extensions
  (all optional for backward compatibility with persisted baseline rows).
- `evidence/risk.py` — hard critical signal gated on verification evidence
  strength (≥0.34) before it can lift the final score.
- `agents/verifier.py` — support matching via typed evidence_ids with
  exact/normalized fallback (list-repr, comma-joined, plain). No substring
  matching.
- `apps/api/main.py` — optional API-key authorization (`VERIFORGE_API_KEY` /
  `X-API-Key`) on history endpoints; `/api/v1/integrations/status`; analyze
  500 responses no longer leak internal exception text.
- `config.py` — `VERIFORGE_API_KEY` setting.
- `evaluation/runner.py` — explicit decision coverage and abstention count.
- `frontend/src/{App.tsx,api.ts,types.ts,styles.css}` — integration status
  badges, evidence strength row, external evidence provenance, memory traces
  with prior-investigation attribution, hypotheses outcomes, incomplete
  banner, inference labels, verification/contradiction panel.
- `.gitignore` — `.hmem/` runtime data excluded.
- `requirements.txt` — pytest-asyncio, pytest-httpx (test-only deps).

## Behavior changes vs baseline

| Area | Baseline | Now |
| --- | --- | --- |
| Unverified critical signal | Could force CRITICAL | Capped: verification support required |
| Evidence support | Substring match | Typed IDs + exact normalized match |
| Benchmark coverage | Ambiguous silently dropped | `decision_coverage`, `abstained_count` reported |
| Analysis history | Open to all | API-key gated when configured |
| 500 responses | Leaked exception text | Generic message; details logged server-side |
| External evidence | None | Zetaris correlation with typed provenance |
| Memory | Stateless | H-MEM with provenance, audit, isolation |
| Sponsor outage | N/A | Incomplete verdict, capped severity |

## Verified results

- Python tests: 119 passed, 1 skipped (live Zetaris, env-gated).
- Frontend: 1 test passed; production build succeeds.
- Benchmark: precision 1.0, recall 0.93, F1 0.929, TN 50/50 — matches the
  baseline's own re-run numbers exactly (the checked-in baseline report was
  stale; measured equivalence verified by worktree re-run at ff32c6c).
- Docker image builds; container serves /ready, integrations status, and a
  full investigation with cross-investigation memory reuse.
