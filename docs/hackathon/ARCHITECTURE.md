# Architecture

## System flow (pipeline v2)

```
content ──► 1. injection screen (trust: trusted/untrusted)
        ──► 2. claim & indicator extraction (offline, deterministic)
        ──► 3. hypothesis generation (explicit, falsifiable)
        ──► 4. Zetaris correlation ─────────► external evidence (typed, provenance)
        ──► 5. H-MEM recall ────────────────► memory traces (attributed)
        ──► 6. specialist agents (identity, infrastructure, social engineering)
        ──► 7. verifier (support / contradiction / unsupported claims)
        ──► 8. bounded re-retrieval (only if evidence missing)
        ──► 9. deterministic risk (Python; hard signals gated on verification)
        ──► 10. evidence-linked explanation + recommended action
        ──► 11. persist analysis + memory updates + telemetry
```

## Components

| Component | Role | Pre-existing / New |
| --- | --- | --- |
| `engine.py` | Pipeline orchestration, failure handling, verdict capping on incomplete | Modified |
| `evidence/extractor.py` | Indicator & claim extraction | Pre-existing |
| `evidence/external.py` | Zetaris correlation, evidence normalization | New |
| `evidence/sanitize.py` | Prompt-injection screening, snippet bounding | New |
| `evidence/risk.py` | Deterministic risk, verification-gated hard signals | Modified |
| `evidence/graph.py` | Claim–evidence–finding graph | Pre-existing |
| `agents/` | Specialist agents + verifier (demo heuristics / Featherless LLM) | Pre-existing (verifier support-matching hardened) |
| `integrations/zetaris/` | Zetaris UI-proxy SQL client, validated templates | New |
| `integrations/featherless.py` | LLM provider | Pre-existing |
| `hmem/` | H-MEM engine: store, retrieval, ledger, conflicts | New |
| `apps/api/main.py` | FastAPI: analyze, authorized history, integrations status, webhooks | Modified |
| `database.py` | SQLite persistence | Pre-existing |
| `frontend/` | React UI: analysis, provenance panels, memory trace, integration badges | Modified |
| `evaluation/` | 150-sample offline benchmark with coverage reporting | Modified |

## Trust boundaries

- Message content is attacker-controlled: screened before LLM/memory use;
  injection-flagged content never reaches long-term memory.
- Zetaris queries are read-only templates; message text never becomes SQL.
- LLM (Featherless) never computes risk; it proposes findings, Python decides.
- Analysis history requires `X-API-Key` when `VERIFORGE_API_KEY` is set.
- Secrets live only in environment/`.env` (git-ignored); none are logged or
  sent to the frontend (status endpoints expose booleans, never values).

## Failure model

| Failure | Behavior |
| --- | --- |
| Zetaris not configured | `not_configured` status; analysis proceeds offline |
| Zetaris unreachable/timeout | `unavailable`/`failed` status; investigation marked incomplete; verdict capped below HIGH |
| H-MEM failure | Logged; analysis proceeds without memory context; incomplete flagged |
| LLM provider down | Demo-mode heuristics remain; live mode returns sanitized 500 (no internal text) |
| Incomplete investigation | Never emits CRITICAL/HIGH |
