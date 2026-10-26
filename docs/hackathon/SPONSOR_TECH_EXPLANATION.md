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

- Route: HTTP SQL through the **UI proxy** (`POST {ZETARIS_BASE_URL}/api/proxy/query`).
  The raw API on port 8888 is deliberately not used.
- Auth: `Authorization: Bearer $ZETARIS_API_KEY` (or username/password token
  exchange), plus `X-Org-ID` and a fresh UUID `X-Request-ID` per request.
- Environment: `ZETARIS_BASE_URL` (UI origin), `ZETARIS_ORG_ID`,
  `ZETARIS_API_KEY` or `ZETARIS_USERNAME`/`ZETARIS_PASSWORD`,
  optional `ZETARIS_QUERY_LIMIT` (default 1000) and `ZETARIS_ENGINE_ID`.
- 30 s timeout, bounded row limits, no retries on 4xx, controlled retry
  budget on transient failures.

**Safety properties.**

- Only `SELECT`/`SHOW`/`DESCRIBE`/`EXPLAIN` statements pass validation; any
  write/DDL keyword is rejected before the request is sent.
- Indicator values are bound through named templates with quote escaping —
  attacker-controlled message content can never become arbitrary SQL.
- When Zetaris is not configured or unreachable, the client returns an
  explicit `not_configured`/`unavailable`/`failed` status; the investigation
  is marked incomplete and the verdict is capped below HIGH/CRITICAL.

**Live status.** `ZETARIS_API_KEY` is present in the environment;
`ZETARIS_BASE_URL` (instance UI origin) was not provisioned at submission
time, so the live acceptance gate (actual query + response against a real
instance) is pending. This is reported honestly in INTEGRATION_STATUS.md —
no mocked response is presented as live evidence. Mocked unit tests and the
outage path are fully green; a live test (`test_zetaris_live_connectivity`)
runs automatically when `ZETARIS_BASE_URL` and `ZETARIS_ORG_ID` are set.

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
