# Implementation Audit

Audit date: 2026-10-27. Baseline reviewed: `507442d715434486ba3f66cd6bc791ff6ba715bc`; pre-hackathon comparison point: `ff32c6cdd5e7762844dda3e80ac8f96e63db681b`.

## Existing functionality

- FastAPI investigation API, deterministic demo pipeline, SQLite persistence, signed Agentboxd ingestion, evidence graph, Featherless adapter, React/Vite interface, offline benchmark, and an in-process H-MEM implementation.
- Read-only Zetaris client and mocked unit coverage existed, but live transport and datasource assumptions required correction.

## Confirmed defects and security risks

- A clean checkout tracked an index-only frontend `dist/` directory. FastAPI eagerly mounted a missing `assets/` directory and failed during import.
- Generated frontend dependencies and build/report artifacts were tracked, making clean checkout and CI unreliable.
- Zetaris rendered SQL identifiers as data literals, used a transport different from the local documented platform, and could report failed attempts as available retrieval.
- Specialist scores could influence risk despite unsupported verification findings.
- The original API had no user identity, tenant isolation, roles, CSRF protection, or object-level authorization. Client context could supply a tenant identifier.
- Existing frontend routes were dashboard/history/detail only. Administrative, onboarding, report, accessibility, and complete failure-state journeys were incomplete.
- Historical documents contained test claims that must be regenerated after final code changes. No live IOC datasource query has been verified.

## Test baseline

| Command | Outcome | Scope |
| --- | --- | --- |
| `PYTHON_DOTENV_DISABLED=true .venv/bin/python -m pytest -q` | 119 passed, 1 skipped (77.15s) | Pre-change Python baseline; skipped live Zetaris test |
| `npm --prefix frontend test` | 1 passed | Pre-change UI smoke coverage |
| `npm --prefix frontend run build` | passed | Pre-change Vite/TypeScript bundle |

## Scope and release blockers

P0 is startup/CI hygiene, evidence/risk safety, and truthful Zetaris health. P1 is authenticated multi-tenant investigations, management workflows, and UI accessibility. The final submission remains blocked until an approved IOC datasource and dedicated read-only Zetaris identity are configured and the env-gated live acceptance test passes. H-MEM must be described accurately as an in-process implementation, not a hosted or certified sponsor service.

The current SQLite upgrade path is an additive, backup-first compatibility
routine in `database.py`; it preserves existing records in the legacy tenant
and is covered by migration-oriented tests, but it is not an Alembic revision
history. That gap is recorded as a release blocker rather than represented as
completion.

## ECC workflow

No ECC Codex plugin was present in this runtime. Native Codex discovery, test-first changes, parallel review, verification, and documentation are being used as the equivalent workflow. Any later ECC installation must use the official marketplace/cache verification guidance and must not duplicate existing adapters.
