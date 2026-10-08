# VeriForge

VeriForge is a ForgeHacks 2026 prototype for analyzing suspicious messages using extracted indicators, specialist analysis, and a deterministic risk calculation. The model is an analysis component; it does not choose the final verdict.

## Current Status

The repository currently contains a FastAPI backend with `GET /health`, `POST /api/v1/analyze`, `GET /api/v1/analyses`, `GET /api/v1/analyses/{id}`, and `POST /api/v1/webhooks/agentboxd`. It extracts URLs, domains, email addresses, urgency terms, credential terms, and financial-action terms, then combines specialist results into a risk score. SQLite stores structured analysis results and evidence for history; there is no dedicated raw-input field.

The backend now returns an evidence-derived graph with extracted claims, observations, findings, and decision links, and accepts signed Agentboxd email events. The repository does not yet include a frontend. Do not treat this prototype as a production security service.

## Architecture Direction

The planned standalone flow is:

Input → normalization → claim extraction → evidence collection → specialist analysis → evidence graph → verification → deterministic risk decision → safe next action → persistence.

The evidence graph represents observed entities, claims, findings, and provenance. Risk remains calculated in Python; configured weights are initial engineering parameters and have not been benchmarked.

## Local Backend

Python 3.10 or newer is recommended. Install dependencies and start the API:

```sh
python -m pip install -r requirements.txt
uvicorn apps.api.main:app --reload
```

The API is available at `http://127.0.0.1:8000`; health check: `GET /health`.

Run the current tests with:

```sh
python -m pytest -q
```

## Configuration

Copy `.env.example` to `.env` for local configuration. `.env` is ignored by Git; never commit credentials. Demo mode defaults to disabled; enable it explicitly only for local offline testing. Featherless calls require `FEATHERLESS_API_KEY`. Agentboxd variables are placeholders for the planned webhook integration and are not currently consumed by an endpoint.

## Security and Limitations

Analyzed content is attacker-controlled. Current prompts label supplied content untrusted, but prompt text alone is not a security boundary. Live model output is validated against Pydantic result models, but API access is not authenticated or rate-limited, and general error handling needs hardening. URL extraction is offline; the backend does not fetch submitted URLs. No Agentboxd email is processed and no email responses are sent.

Risk weights and demo heuristics are prototype choices, not scientifically validated thresholds. There is no benchmark dataset or measured performance report yet. See [the threat model](docs/threat-model.md) and [the architecture notes](docs/architecture.md) for current gaps and planned boundaries.

## Roadmap

The remaining implementation is phased: React frontend and graph visualization; evaluation; security hardening; then Docker, CI, and deployment documentation. Features are not claimed as complete until their tests and runtime checks pass.

## Hackathon

Project: ForgeHacks 2026, AI + Cybersecurity. Before submission, provide a working deployment, screenshots, a 2–4 minute demo, and a project description. No public deployment or performance results are claimed here.
