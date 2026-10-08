# VeriForge

VeriForge is a ForgeHacks 2026 prototype for analyzing suspicious messages using extracted indicators, specialist analysis, and deterministic risk scoring. The system is evidence-first: the model interprets signals, while Python validates outcomes and calculates the final decision.

## Current implementation status

The repository contains:

- A FastAPI backend with health, readiness, analysis, history, and Agentboxd webhook endpoints
- A React/Vite frontend for local interaction and scenario-driven demos
- An offline evaluation runner and benchmark dataset for reproducible verification
- SQLite persistence for analyses, evidence, findings, and webhook events
- A hardened API layer with request-size checks, rate limiting, safe error contracts, and security headers
- Demo-mode behavior for offline local runs and verified provider validation for live execution

This project is a prototype and should not be treated as a production-grade security service without additional operational controls, deployment review, and domain-specific validation.

## Architecture flow

Input → normalization → claim extraction → evidence collection → specialist analysis → evidence graph → verification → deterministic risk decision → persistence

The evidence graph represents observed entities, claims, findings, and provenance. Risk calculations remain deterministic and are implemented in Python rather than delegated to the model.

## Local setup

Python 3.10 or newer is recommended.

```sh
python -m pip install -r requirements.txt
uvicorn apps.api.main:app --reload
```

The API is available at `http://127.0.0.1:8000`.

Useful checks:

```sh
python -m pytest -q
python -m evaluation.runner
```

## Configuration

Copy `.env.example` to `.env` for local configuration. `.env` is ignored by Git; never commit credentials or secrets.

Required production variables include:

- `DEMO_MODE`
- `FEATHERLESS_API_KEY` when demo mode is disabled
- `FEATHERLESS_BASE_URL`
- `FEATHERLESS_MODEL`
- `AGENTBOXD_WEBHOOK_SECRET` for signed webhook verification

For local offline work, keep `DEMO_MODE=true` and avoid live provider dependencies.

## Security notes

- Analyzed content is attacker-controlled and should be treated as untrusted input.
- Webhook signatures are verified against the documented Agentboxd raw-body contract before parsing.
- API responses use a safe error envelope and do not expose internal failure details.
- Request size and request rate are constrained at the ingress layer.
- URL extraction is offline; the backend does not fetch or validate remote destinations on its own.

See [docs/threat-model.md](docs/threat-model.md) and [docs/architecture.md](docs/architecture.md) for the system boundaries and current assumptions.

## Deployment and CI

A Docker container and a GitHub Actions workflow are included so the repo can be validated in CI and started in a containerized environment.

Docker quick start:

```sh
docker build -t veriforge .
docker run --rm -p 8000:8000 --env-file .env veriforge
```

Compose quick start:

```sh
docker compose up --build
```

The workflow in `.github/workflows/ci.yml` runs the Python test suite automatically on pushes and pull requests.

## Submission materials

The final submission checklist is in [docs/submission-checklist.md](docs/submission-checklist.md).

## Hackathon guidance

Project: ForgeHacks 2026, AI + Cybersecurity. Before submission, validate the working deployment, capture screenshots, and provide a short 2–4 minute live walkthrough of the evidence-first workflow without overstating claims about production readiness or security guarantees.
