# Test Evidence

Every entry records the exact command, result, and limitations. Skipped/gated tests are marked, never claimed as passed.

## Baseline (commit ff32c6c, 2026-10-26 05:00 UTC)

| Suite | Command | Result | Limitations |
| --- | --- | --- | --- |
| Python unit/API/integration | `PYTHON_DOTENV_DISABLED=true python -m pytest -q` | **63 passed** in 4.73s | Demo-mode heuristics only; no live LLM |
| Frontend unit | `cd frontend && npm test` | **1 passed** | Single smoke test — thin coverage (pre-existing) |
| Frontend build | `cd frontend && npm run build` | **PASS** (tsc + vite, 2.58s) | — |
| Offline benchmark | `python -m evaluation.runner` | Ran; binary precision/recall/F1 = 1.0000; **TN=45 of 50 benign** | Coverage artifact: ambiguous observed labels are silently dropped from metrics (defect D3); fixture-based, not live accuracy |
| Docker Compose | — | NOT RUN at baseline | Will run in release verify |

## New work

Appended as phases land.
