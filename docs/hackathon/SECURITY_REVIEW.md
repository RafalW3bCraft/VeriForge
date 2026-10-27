# Security Review

## Implemented controls

- Opaque hashed sessions, Argon2 password hashes, HTTP-only cookies, session expiration, login throttling, CSRF validation, and constant-time shared API-key comparison.
- Server-side tenant, ownership, role, and explicit-grant checks for investigation list/detail/export/share/review/archive routes.
- Prompt-injection screening, bounded request size/rate controls, signed Agentboxd webhook validation, safe error responses, and untrusted-content sanitization.
- Registered Zetaris datasource identifiers, fixed read-only query shape, normalized indicator lookup, bounded query settings, strict response parsing, and redacted integration health.
- Risk escalation now requires evidence-linked verification support; unsupported model claims cannot create an authoritative critical verdict.

## Remaining limitations

- This is a prototype, not a certified security service. The in-memory rate limiter is per process.
- A live Zetaris IOC test is intentionally gated until a dedicated account and approved datasource are provisioned.
- The current compatibility migration is additive SQLite schema setup rather than
  an Alembic revision chain; take a verified backup before upgrade and do not
  treat it as production migration governance.
- H-MEM is an in-process implementation of applicable contracts, not a hosted Meterless service or a claimed certification.
- Deployment requires HTTPS, secret management, backup/restore exercises, and environment-specific monitoring.
