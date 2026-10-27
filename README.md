# VeriForge

VeriForge is an evidence-first investigation agent for suspicious messages. It extracts indicators, forms explicit hypotheses, corroborates them against external threat data through **Zetaris**, recalls trusted context from its **Meterless H-MEM** memory, runs specialist analyses, verifies which findings are actually supported, and calculates the final risk deterministically in Python — outside the LLM. Every verdict ships with typed evidence references, hypothesis outcomes, memory provenance, and honest incomplete-investigation states when an integration is down.

The project includes a FastAPI API, a React/Vite frontend, SQLite analysis history, a signed Agentboxd webhook endpoint, an offline evaluation runner, and the two sponsor integrations. It is not a production-grade security service; do not use its verdicts as the sole basis for security decisions.

Hackathon submission materials (baseline disclosure, integration status, test evidence, demo script) live in [docs/hackathon/](docs/hackathon/).

## Quick Start: Local App

Requirements: Python 3.10+, pip, and Node.js 22 with npm. The commands below are for Linux/macOS; use the equivalent virtual-environment activation command on Windows.

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
test -f .env || cp .env.example .env
cd frontend
npm ci
npm run build
cd ..
uvicorn apps.api.main:app --reload
```

`.env.example` sets `DEMO_MODE=true`, so this starts offline without provider credentials. Open <http://127.0.0.1:8000> for the built-in web app. The API health endpoints are <http://127.0.0.1:8000/health> and <http://127.0.0.1:8000/ready>; interactive API documentation is at <http://127.0.0.1:8000/docs>.

If you skip creating `.env`, `DEMO_MODE` defaults to `false` and the API will require `FEATHERLESS_API_KEY` before starting.

## Frontend Development

Run the backend from the repository root as above. In a second terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open <http://localhost:5173>. Vite proxies `/api` and `/health` requests to the backend on port 8000. Node.js 22 is used for the frontend build in Docker.

## Tests And Evaluation

Run the Python unit, API, integration, persistence, and evaluation tests:

```sh
PYTHON_DOTENV_DISABLED=true python -m pytest -q
```

This keeps machine-specific values in `.env` from changing test defaults; it does not modify `.env`.

Run the frontend test, TypeScript check, and production build:

```sh
cd frontend
npm ci
npm test
npm run build
```

Run the full 150-sample offline benchmark from the repository root:

```sh
python -m evaluation.runner
```

The benchmark forces demo mode and writes reports to `.artifacts/latest_report.json` and `.artifacts/latest_report.md`. These are generated outputs; inspect the new report for current results. Benchmark results are fixture-based and do not establish live threat-detection accuracy.

GitHub Actions currently runs the Python test suite. Frontend tests and build are available locally with the commands above.

## Configuration

Copy `.env.example` to `.env` before starting the app or using Compose. `.env` is ignored by Git; never commit credentials.

| Variable | Purpose |
| --- | --- |
| `DEMO_MODE` | `true` uses offline heuristics; `false` enables Featherless analysis. Defaults to `false` if unset. |
| `FEATHERLESS_API_KEY` | Required when `DEMO_MODE=false`. |
| `FEATHERLESS_BASE_URL`, `FEATHERLESS_MODEL` | Provider endpoint and model; defaults are in `.env.example`. |
| `AGENTBOXD_WEBHOOK_SECRET` | Required to enable signed webhook verification. |
| `DATABASE_URL` | SQLAlchemy database URL; defaults to local SQLite. Compose stores SQLite data in a named volume. |
| `CORS_ORIGINS` | Comma-separated browser origins allowed by the API. |
| `RATE_LIMIT`, `MAX_INPUT_CHARS`, `MAX_REQUEST_BYTES` | Request limits. |
| `RETENTION_DAYS` | Retention window for saved analyses and webhook metadata. |
| `RISK_WEIGHT_IDENTITY`, `RISK_WEIGHT_INFRASTRUCTURE`, `RISK_WEIGHT_SOCIAL`, `RISK_WEIGHT_VERIFICATION` | Nonnegative risk weights; their sum must equal 1. |
| `VERIFORGE_BOOTSTRAP_ADMIN_USERNAME`, `VERIFORGE_BOOTSTRAP_ADMIN_PASSWORD` | Enables local-account mode and creates the first tenant administrator. Set both explicitly; there is no public signup. |
| `VERIFORGE_SESSION_HOURS`, `VERIFORGE_SESSION_COOKIE_SECURE` | Session lifetime and secure-cookie policy. Keep secure cookies enabled behind HTTPS. |
| `ZETARIS_BASE_URL`, `ZETARIS_ORG_ID`, and either `ZETARIS_API_KEY` or `ZETARIS_USERNAME`/`ZETARIS_PASSWORD` | Dedicated read-only Zetaris identity. The app runs offline and reports `not_configured` when this is absent. |
| `ZETARIS_IOC_DATASOURCE`, `ZETARIS_IOC_DOMAIN_COLUMN`, `ZETARIS_IOC_RECORD_ID_COLUMN` | Approved registered IOC datasource mapping. Identifiers are validated; the UI cannot supply SQL. |
| `ZETARIS_QUERY_LIMIT`, `ZETARIS_TIMEOUT_SECONDS` | Zetaris query bounds and timeout. |
| `AGENTBOXD_TENANT_ID` | Server-configured tenant for signed Agentboxd deliveries; it is never read from webhook content. |
| `HMEM_DATA_DIR` | H-MEM memory persistence directory; defaults to `./.hmem`. |

Additional timeout, retry, and logging settings are defined in [config.py](config.py). For live analysis, set `DEMO_MODE=false` and provide a valid `FEATHERLESS_API_KEY`. Configure `AGENTBOXD_WEBHOOK_SECRET` only when accepting signed webhook events. See [docs/FEATHERLESS.md](docs/FEATHERLESS.md) and [docs/AGENTBOXD.md](docs/AGENTBOXD.md).

## Docker Deployment

For a local containerized demo, from the repository root:

```sh
test -f .env || cp .env.example .env
docker compose up --build
```

The app is available at <http://127.0.0.1:8000>. Compose defaults to demo mode and persists the SQLite database in the `veriforge-data` named volume. Set `DEMO_MODE=false` and `FEATHERLESS_API_KEY` in `.env` to use the live provider. Stop the app with `docker compose down`; the named database volume remains. To delete the database as well, run `docker compose down --volumes`.

To build and run the image without Compose:

```sh
docker build -t veriforge .
docker run --rm -p 8000:8000 --env-file .env \
	-v veriforge-data:/app/data \
	-e DATABASE_URL=sqlite:////app/data/veriforge.db \
	veriforge
```

This is a local prototype and must not be deployed publicly. Local-account mode provides Argon2 password hashes, opaque server-side sessions in HttpOnly cookies, CSRF checks, and tenant-scoped roles when explicit bootstrap credentials are configured. A trusted HTTPS reverse proxy, secret management, database backups, monitoring, stronger rate limiting, and a deployment review are still required before any real deployment. Review [docs/threat-model.md](docs/threat-model.md) before handling real messages.

## Troubleshooting Persistence Errors

If analysis returns `Analysis result could not be persisted`, rebuild and recreate the Compose service:

```sh
docker compose up --build -d
curl -fsS http://127.0.0.1:8000/ready
```

Repeated messages can contain the same stable evidence IDs. Database evidence records are now scoped to their analysis, so repeated analyses no longer collide. This fix keeps existing database rows; do not run `docker compose down --volumes`, which deletes saved history.

## System Flow

Input → injection screening → claim extraction → hypotheses → Zetaris correlation → H-MEM recall → specialist analysis → evidence graph → verification → bounded re-retrieval → deterministic risk decision (verification-gated) → persistence + memory updates.

The backend does not fetch or validate remote URL destinations. The model is not given tools to execute message instructions; message content is screened for prompt injection and injection-flagged content never reaches high-trust memory. Sponsor systems report truthful availability status; investigations degraded by an outage are marked incomplete and their verdicts are capped.

### Sponsor integrations

- **Zetaris** (`integrations/zetaris/`): fixed, read-only lookup templates use the documented UI proxy route and an allowlisted datasource mapping. It requires `ZETARIS_BASE_URL` (UI origin), `ZETARIS_ORG_ID`, dedicated read-only credentials, and the approved IOC mapping. Without them it reports `zetaris: not_configured` — never a mocked success. A successful zero-match query means “no corroborating records,” not provider failure.
- **Meterless H-MEM** (`hmem/`): in-process implementation of the official H-MEM contracts — tiered store, hybrid retrieval with trace, trust ledger, conflict detection, tenant/investigation isolation. Persists to `./.hmem/` (override with `HMEM_DATA_DIR`). Dreaming/sleep cycles are documented as not implemented.

With local accounts configured, the backend derives tenant, role, ownership, and grants exclusively from the server-side session. The legacy `VERIFORGE_API_KEY` is retained only as a migration aid for single-user local mode.

## Project Docs

- [Architecture](docs/architecture.md)
- [Threat model](docs/threat-model.md)
- [Evaluation details](docs/evaluation.md)
- [Submission checklist](docs/submission-checklist.md)
- [Implementation audit](docs/hackathon/IMPLEMENTATION_AUDIT.md)
- [User guide](docs/hackathon/USER_GUIDE.md)
- [Administrator guide](docs/hackathon/ADMIN_GUIDE.md)
- [Security review](docs/hackathon/SECURITY_REVIEW.md)
- [Release report and blockers](docs/hackathon/FINAL_RELEASE_REPORT.md)
