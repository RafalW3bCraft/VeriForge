# Integration Status

## Zetaris — implemented, live IOC verification blocked

VeriForge uses only the Zetaris UI proxy endpoint `POST /api/proxy/query/sql/start` with `select` and `pageLimit`. It does not call the raw API or permit arbitrary SQL.

The integration requires a dedicated read-only identity plus these runtime mappings: `ZETARIS_BASE_URL`, `ZETARIS_ORG_ID`, credentials, `ZETARIS_IOC_DATASOURCE`, `ZETARIS_IOC_DOMAIN_COLUMN`, and `ZETARIS_IOC_RECORD_ID_COLUMN`. Datasource and column identifiers are strictly validated; values are normalized hostnames and safely represented in fixed read-only query templates.

- Mocked transport/correlation coverage: implemented.
- Live acceptance test: `RUN_LIVE_ZETARIS_TESTS=1 ... pytest tests/test_zetaris.py -q`.
- Live evidence: **not verified**. The local Zetaris platform was inspected but not running, and no approved IOC datasource/read-only account was supplied to this application.
- Submission impact: mandatory sponsor evidence remains blocked until that test passes.

## Meterless H-MEM — local implementation, not hosted certification

The `hmem/` package persists canonical memory records, retrieval traces, trust ledger entries, conflicts, supersession, and tenant/investigation scoping in-process. It is tested as a Python implementation of applicable H-MEM concepts. It is not represented as a Meterless-hosted API, official certification, or proof of sponsor acceptance. Dreaming/sleep-cycle features remain out of scope.

## Featherless and Agentboxd

Featherless remains optional for live reasoning; offline demo-mode tests do not establish live-provider behavior. Agentboxd ingestion retains signed webhook verification and replay/idempotency protections; it must be server-configured to an owning tenant in account mode before production use.
