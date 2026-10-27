# Setup and Demo

## Prerequisites

- Python 3.10+ and pip; Node.js 22 + npm; or Docker (29+).
- No sponsor credentials are needed for the offline demo (`DEMO_MODE=true`).
- Live Zetaris requires the participant's own instance: set
  `ZETARIS_BASE_URL` (UI origin), `ZETARIS_ORG_ID`, either dedicated
  read-only credential form, and the approved IOC datasource/column mapping.

## Local run (verified)

```sh
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env   # DEMO_MODE=true by default
cd frontend && npm ci && npm run build && cd ..
uvicorn apps.api.main:app --reload
```

Open http://127.0.0.1:8000 — analyze a message, inspect the verdict,
evidence strength, hypotheses, integration status and memory traces.

## Docker (verified — image builds and serves)

```sh
docker build -t veriforge .
docker run --rm -p 8000:8000 -e DEMO_MODE=true veriforge
curl -fsS http://127.0.0.1:8000/ready
curl -fsS http://127.0.0.1:8000/api/v1/integrations/status
```

Compose uses migration-on-start, non-root runtime, health checks, and named
SQLite/H-MEM volumes. Validate its configuration with `docker compose config --quiet`
before starting it.

## Tests (all commands verified)

```sh
PYTHON_DOTENV_DISABLED=true .venv/bin/python -m pytest -q
cd frontend && npm ci && npm test && npm run build
python -m evaluation.runner                       # benchmark -> .artifacts/
```

The single skipped test is the live Zetaris connectivity check — it runs
automatically when `ZETARIS_BASE_URL` and `ZETARIS_ORG_ID` are set.

## Acceptance gates

### H-MEM memory reuse (demonstrated)

```sh
# investigation 1
curl -fsS -X POST localhost:8000/api/v1/analyze -H 'Content-Type: application/json' \
  -d '{"content":"Urgent: account suspended. Verify at https://phish-site-one.example/login now."}'
# investigation 2 — response.memory_traces contains investigation 1's memory,
# attributed via from_investigation_id and provenance_label
curl -fsS -X POST localhost:8000/api/v1/analyze -H 'Content-Type: application/json' \
  -d '{"content":"Another warning about https://phish-site-one.example — confirm credentials."}'
```

Verified live in Docker: second response included
`memory_traces[0].content = "Investigation 5673d389…: CRITICAL …"` with
`from_investigation_id` matching the first analysis.

### Zetaris (pending live instance URL)

Mocked contract tests pass (`tests/test_zetaris.py`). Live gate: configure the
approved datasource and read-only credentials, then:

```sh
RUN_LIVE_ZETARIS_TESTS=1 .venv/bin/python -m pytest \
  tests/test_zetaris.py::test_live_registered_datasource_normalized_lookup_contract -q
curl -fsS localhost:8000/api/v1/integrations/status   # zetaris.status = available
```

Until then the UI and API truthfully report `zetaris: not_configured`.
