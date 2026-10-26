# Integration Status

Updated continuously. "Live" means a real network call against a real sponsor system with real credentials — never a mock.

## Zetaris

- Credential presence: `ZETARIS_API_KEY` present in `.env` (value never read or logged).
- Instance URL: NOT configured (`ZETARIS_URL` absent) — live connectivity BLOCKED on user provisioning.
- Documented access routes (from zetaris/getting-started): SQL Editor, agent JDBC, HTTP helpers using **UI proxy routes** ("the raw API URL is not a substitute"), auth via `.env.local` per scripts/HOWTO.md.
- Implementation route chosen: HTTP helper (SQL over UI proxy), read-only `SELECT` via validated templates.
- Status: IMPLEMENTED — `integrations/zetaris/` client with validated read-only templates, auth headers (Bearer + X-Org-ID + X-Request-ID), 30s timeout, bounded limits, explicit not_configured/unavailable/failed statuses, injection rejection. 12 mocked unit tests green; live test env-gated.
- Live evidence: PENDING (blocked on participant instance URL `ZETARIS_BASE_URL`). Outage path verified: investigation marked incomplete, verdict capped, status truthful.

## Meterless H-MEM

- Nature of dependency: architecture spec + runnable TS reference implementation (Apache-2.0), not a hosted API. The repo explicitly directs implementers to build the contracts in their own stack.
- Implementation route chosen: in-process Python engine (`hmem/`) implementing the canonical memory record, tiered store, hybrid retrieval with trace, trust ledger, conflict/supersede semantics; conformance suite run where compatible.
- Dreaming/sleep cycles: excluded from critical path (spec marks them opt-in).
- `METERLESS_API_KEY` present in `.env` but unused by the reference implementation (no hosted endpoint documented); recorded as unused unless Meterless publishes a service.
- Status: IMPLEMENTED — `hmem/` package (store, retrieval, ledger, conflicts, engine) with 23 conformance-style tests green; acceptance gate (cross-investigation memory reuse with attribution) demonstrated live in Docker.
- Not implemented (documented, spec-optional): dreaming cycle, sleep cycle. Embedding-backed semantic search uses the spec's model-free fallback instead.

## Featherless (pre-existing)

- Unchanged. Used as the LLM provider when `DEMO_MODE=false`. Not a hackathon sponsor.

## Cursor / NVIDIA

- Cursor: not used. Recorded per rules.
- NVIDIA: no enhancement planned; optional per rules.
