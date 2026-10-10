# VeriForge

VeriForge is a prototype for evidence-first analysis of suspicious messages. It extracts indicators, runs specialist analyses, verifies findings against extracted evidence, and calculates the final risk score deterministically in Python.

The project includes a FastAPI API, a React/Vite frontend, SQLite analysis history, a signed Agentboxd webhook endpoint, and an offline evaluation runner. It is not a production-grade security service; do not use its verdicts as the sole basis for security decisions.

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

Before exposing this prototype publicly, provide HTTPS through a trusted reverse proxy, authentication and access controls, secret management, database backups, monitoring, and deployment-specific rate limiting. The API does not provide user authentication, and the built-in rate limiter is in-memory and per process. Review [docs/threat-model.md](docs/threat-model.md) before handling real messages.

## Troubleshooting Persistence Errors

If analysis returns `Analysis result could not be persisted`, rebuild and recreate the Compose service:

```sh
docker compose up --build -d
curl -fsS http://127.0.0.1:8000/ready
```

Repeated messages can contain the same stable evidence IDs. Database evidence records are now scoped to their analysis, so repeated analyses no longer collide. This fix keeps existing database rows; do not run `docker compose down --volumes`, which deletes saved history.

## System Flow

Input → normalization → claim extraction → specialist analysis → evidence graph → verification → deterministic risk decision → persistence.

URL extraction is offline: the backend does not fetch or validate remote destinations. The model is not given tools to execute message instructions or access external evidence.

## Project Docs

- [Architecture](docs/architecture.md)
- [Threat model](docs/threat-model.md)
- [Evaluation details](docs/evaluation.md)
- [Submission checklist](docs/submission-checklist.md)
