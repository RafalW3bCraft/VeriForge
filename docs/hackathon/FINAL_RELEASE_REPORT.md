# Final Release Report

Status: **NOT READY — BLOCKERS REMAIN**

Audit date: 2026-10-27. Baseline: `507442d715434486ba3f66cd6bc791ff6ba715bc`.
Comparison point: `ff32c6cdd5e7762844dda3e80ac8f96e63db681b`.

## New-work disclosure

This release adds guarded SPA asset mounting, generated-artifact de-tracking,
truthful Zetaris transport/health handling, evidence-linked risk gating, local
accounts with tenant-scoped RBAC, an operational React workspace, non-root
container startup, CI jobs, benchmark provenance, and the documentation in
this directory. It does **not** claim a live Zetaris result, a live
Featherless result, hosted H-MEM, public deployment, or hackathon submission.

## Feature-completion matrix

| Area | Complete / total | Percent | Status |
| --- | ---: | ---: | --- |
| P0 correctness and reproducibility | 7 / 8 | 88% | Static mount, hygiene, fixed datasource template, transport, health contract, truthful aggregation, risk/benchmark work complete; live acceptance is blocked. |
| P1 secure workspace | 7 / 10 | 70% | Local accounts, sessions/CSRF, RBAC, tenant isolation, investigations, grants, exports, workspace, and admin view complete; Alembic migrations, datasource metadata management, and full server-side history filtering remain. |
| CI/container verification | 5 / 7 | 71% | Python/Node jobs, hygiene, Compose validation, non-root image and smoke complete; live-provider gates and independently captured dependency/secret-scan results remain. |
| Documentation/submission | 5 / 7 | 71% | Guides, audit, security review, test evidence, demo route, and release report complete; demo video/slide deck and live sponsor evidence are outstanding. |
| **Overall** | **24 / 32** | **75%** | **Not release-ready.** |

Percentages are simple completed-checklist-items divided by total checklist
items; they are not test pass rates.

## Reproducible demo sequence

1. Set `DEMO_MODE=true`; build the frontend and start the local image or
   Compose stack.
2. Visit the dashboard and confirm Zetaris displays `not_configured` unless
   approved runtime configuration has been supplied.
3. Sign in with the explicit bootstrap administrator only when account mode is
   configured; otherwise use legacy local-demo mode.
4. Create an investigation, inspect the plain-language verdict, incomplete
   warning, evidence table, provenance, and memory attribution.
5. Export JSON or print the report. As an administrator, open Administration
   to view non-secret integration health, provision a local user, and inspect
   redacted audit metadata.
6. Do not describe demo-mode results or mocked provider tests as live sponsor
   verification.

## Release blockers

1. Provision a dedicated read-only Zetaris identity and approved IOC
   datasource/schema via runtime variables, then pass the env-gated normalized
   live lookup and UI presentation acceptance test.
2. Replace the current additive SQLite upgrade/bootstrap routine with the
   required Alembic migration history, including the documented backup/restore
   migration exercise.
3. Capture a clean-environment final test run, dependency/secret scans, Docker
   and Compose runtime checks, and any live-provider results in
   `TEST_EVIDENCE.md`.
4. Create the required demo video/slide deck and submit only after the gates
   above are satisfied.

See [TEST_EVIDENCE.md](TEST_EVIDENCE.md) for commands and limitations, and
[INTEGRATION_STATUS.md](INTEGRATION_STATUS.md) for sponsor-integration truth.
