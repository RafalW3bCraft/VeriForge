# Sponsor Technology Explanation

## Zetaris (external evidence correlation)

**What it does in VeriForge.** When a message is investigated, extracted
indicators (domains, URLs, sender addresses) are looked up in threat-intel
datasets hosted in the participant's Zetaris instance. Returned records become
typed evidence with source name, record id, query reference, retrieval time
and observed status. Corroborated indicators can raise a verdict;
uncorroborated ones leave hypotheses explicitly "unverified".

**How it is connected (documented route only).** Implementation follows
`zetaris/getting-started` (`scripts/HOWTO.md`, `docs/connections/README.md`):

- Route: HTTP SQL through the **UI proxy** (`POST {ZETARIS_BASE_URL}/api/proxy/query/sql/start`).
  The raw API on port 8888 is deliberately not used.
- Auth: `Authorization: Bearer $ZETARIS_API_KEY` (or username/password token
  exchange), plus `X-Org-ID` and a fresh UUID `X-Request-ID` per request.
- Environment: `ZETARIS_BASE_URL` (UI origin), `ZETARIS_ORG_ID`,
  `ZETARIS_API_KEY` or `ZETARIS_USERNAME`/`ZETARIS_PASSWORD`,
  `ZETARIS_IOC_DATASOURCE`, IOC columns, optional `ZETARIS_QUERY_LIMIT`
  (bounded to 250), and `ZETARIS_ENGINE_ID`.
- 30 s timeout, bounded row limits, no retries on 4xx, controlled retry
  budget on transient failures.

**Safety properties.**

- The client has no general SQL entry point: it emits one fixed `SELECT`
  template against an administrator-registered, identifier-validated IOC
  datasource. Write/DDL statements cannot be selected by the UI or caller.
- The documented proxy accepts `select` text rather than query parameters, so
  normalized values are safely encoded as SQL literals in that fixed template;
  they never select identifiers or alter SQL structure.
- When Zetaris is not configured or unreachable, the client returns an
  explicit `not_configured`/`degraded`/`failed` status; the investigation
  is marked incomplete and the verdict is capped below HIGH/CRITICAL.

**Live status.** No live IOC claim is made. The acceptance gate needs a
participant-provided UI origin, dedicated read-only identity, and approved IOC
mapping. This is reported in INTEGRATION_STATUS.md; mocked transport and
outage tests are not presented as live evidence. The acceptance test runs only
when `RUN_LIVE_ZETARIS_TESTS=1`, all mapping settings, and either API-key or
username/password credentials are supplied.

## Meterless H-MEM (agent memory)

**What it does in VeriForge.** Every investigation's trusted conclusions are
stored as H-MEM memory records. The next investigation about the same
indicator retrieves them — with provenance and a retrieval trace — so the
agent can say "I flagged this domain yesterday, here is the investigation,
and here is why I am surfacing it now."

**Implementation approach.** H-MEM is an architecture spec, not a hosted
service; the official repo instructs implementers to build the contracts in
their own stack ("The contracts do not change"). VeriForge implements them
in-process in Python (`hmem/`), following `engines/hmem/AGENTS.md`:

- Canonical memory record: `source` mandatory (rejected by construction),
  `provenance` (origin, learned-at, human-readable label, refs), layer,
  confidence, entities, `supersedes`/`supersededBy`, `derivedFrom`.
- Tiered store: short_term (volatile), working + long_term (persisted to
  JSON; SQLite backing is a noted enhancement).
- Hybrid retrieval implementing the spec formula:
  `0.35·semantic + 0.20·keyword + 0.10·tag + 0.10·domain + 0.15·entity +
   0.05·layer + 0.05·recency − 0.20·superseded`, then `clamp01(raw) ×
  confidence`, top-5. Semantic uses a model-free token-cosine fallback
  (spec §4.3 graceful degradation); the fallback retrieval threshold (0.10)
  is documented against the spec's embedding-tuned 0.35.
- Trust ledger: append-only audit of every mutation (create/read/delete/
  feedback/conflict events).
- Feedback deltas exactly per spec §9.2 (+0.05 / −0.03 / −0.20 + review tag).
- High-trust floor: memories below confidence 0.70 cannot enter long_term —
  unverified, untrusted content never becomes durable knowledge.
  Prompt-injection-flagged input is never promoted to long_term.
- Isolation: retrieval never crosses tenant boundaries; investigation-scoped
  memories are correlated across a tenant's investigations only via the
  explicit, attributed `include_related` path; a strict single-investigation
  scope is one flag away.
- Conflicts: opposing-phrase and shared-entity heuristics detect
  contradictions; `supersedes` suppresses false conflicts; auto-resolution
  is gated at decision confidence ≥ 0.70, losers are marked `supersededBy`
  (penalized, never deleted).

**Not implemented (documented, spec-optional).** Dreaming cycle, sleep cycle.
The official TS conformance runner targets TypeScript implementations;
VeriForge instead ships conformance-style pytest coverage of the same
contracts (23 tests in `tests/test_hmem.py`).

**Acceptance gate (demonstrated).** Two sequential investigations about the
same phishing domain: the second retrieves the first investigation's memory
with attribution (verified in `test_sequential_investigations_reuse_memory`
and live in the Docker demo — see SETUP_AND_DEMO.md).
