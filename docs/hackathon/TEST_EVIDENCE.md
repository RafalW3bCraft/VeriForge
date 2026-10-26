# Test Evidence

Every entry records the exact command, result, and limitations. Skipped/gated tests are marked, never claimed as passed.

## Baseline (commit ff32c6c, audited 2026-10-26 05:00 UTC)

| Suite | Command | Result | Limitations |
| --- | --- | --- | --- |
| Python unit/API/integration | `PYTHON_DOTENV_DISABLED=true python -m pytest -q` | **63 passed** in 4.73s | Demo-mode heuristics only; no live LLM |
| Frontend unit | `cd frontend && npm test` | **1 passed** | Single smoke test — thin coverage (pre-existing) |
| Frontend build | `cd frontend && npm run build` | **PASS** (tsc + vite, 2.58s) | — |
| Offline benchmark | `python -m evaluation.runner` | Ran; checked-in report showed F1 1.0, TN=45 | Report was stale: re-run at ff32c6c in a clean worktree gave F1 0.929, TN=50, FN=10 |
| Docker Compose | — | NOT RUN | Compose plugin unavailable on this host |

## New work (HEAD, verified 2026-10-26)

| Suite | Command | Result | Limitations |
| --- | --- | --- | --- |
| Full Python suite | `PYTHON_DOTENV_DISABLED=true python -m pytest -q` | **119 passed, 1 skipped** in 7–62s | Skipped = live Zetaris connectivity (env-gated, never claimed) |
| — Zetaris unit | `pytest tests/test_zetaris.py` | 12 passed (mocked HTTP) | Live test skipped without `ZETARIS_BASE_URL`/`ZETARIS_ORG_ID` |
| — H-MEM contracts | `pytest tests/test_hmem.py` | 23 passed | Conformance-style pytest coverage; official TS runner targets TS impls |
| — Pipeline v2 + security | `pytest tests/test_pipeline_v2.py tests/test_api_security.py` | 14 passed | Covers injection screening, outage, auth, memory reuse gate, isolation |
| Frontend unit | `npm test` | **1 passed** | Coverage still thin (pre-existing pattern) |
| Frontend build | `npm run build` | **PASS** (2.6–2.7s) | — |
| Offline benchmark | `python -m evaluation.runner` | precision 1.0, recall 0.933, F1 0.929, TN 50/50, FN 10, decision_coverage 1.0 | **Identical to baseline re-run** — no regression; abstentions now reported |
| Docker image | `docker build -t veriforge-test .` | **PASS** | Compose plugin absent on host; `docker run` verified instead |
| Container runtime | `docker run -p 18000:8000 veriforge-test` + curl | /ready OK; `/api/v1/integrations/status` truthful; analyze → CRITICAL 90.0; second message → memory_traces attributed to first investigation (id 5673d389) | H-MEM acceptance gate demonstrated live |
| Secret scan | grep for key-shaped strings in committed files | Clean | `.env`, `.hmem/` git-ignored |

## Not run (honest list)

- Live Zetaris query/response acceptance gate — blocked on participant
  instance URL provisioning (`ZETARIS_BASE_URL`).
- `docker compose up` — compose plugin not installed on the build host;
  the same image was verified via `docker build` + `docker run`.
- Live Featherless (LLM) path — demo-mode heuristics tested; provider path
  unchanged from baseline.
