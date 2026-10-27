# VeriForge Administrator Guide

## Enable local accounts

Set `VERIFORGE_BOOTSTRAP_ADMIN_USERNAME` and a 12+ character `VERIFORGE_BOOTSTRAP_ADMIN_PASSWORD` before first startup. Set `VERIFORGE_SESSION_COOKIE_SECURE=false` only for localhost HTTP development; production HTTPS must retain the secure default.

There is no public registration. Sign in as the bootstrap administrator, create analyst/viewer accounts, and use the audit endpoint to review redacted administrative actions. Administrators are scoped to their tenant.

## Operations

- `/health` reports process health and `/ready` checks persistence availability.
- `/api/v1/integrations/status` exposes non-secret connector state. A configured connection is not proof of a successful query.
- Back up the SQLite database and H-MEM data directory together before upgrades. Existing records are migrated into the legacy tenant; do not delete the database to upgrade.
- Configure Zetaris only with a dedicated read-only identity and approved IOC datasource mapping. Never copy the local platform administrator `.env` into VeriForge.

## Retention

`RETENTION_DAYS` controls the existing cleanup policy. Retention removes expired analyses and associated evidence; confirm organizational retention requirements and take a backup first.
