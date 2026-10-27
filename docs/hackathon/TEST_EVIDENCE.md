# Test Evidence

Audit date: 2026-10-27. All results below are local evidence, not hosted-CI
or live-provider evidence. Generated benchmark reports are written to the
ignored `.artifacts/` directory and never checked in as release proof.

## Baseline

The pre-change local baseline was commit
`507442d715434486ba3f66cd6bc791ff6ba715bc`; the required comparison point is
`ff32c6cdd5e7762844dda3e80ac8f96e63db681b`.

| Check | Command | Result |
| --- | --- | --- |
| Python baseline | `PYTHON_DOTENV_DISABLED=true .venv/bin/python -m pytest -q` | 119 passed, 1 skipped in 77.15s |
| Frontend baseline | `npm --prefix frontend test` | 1 passed |
| Frontend production build | `npm --prefix frontend run build` | passed |

System Python did not have pytest; all Python commands use the repository
`.venv`. The skipped test is the intentionally env-gated live Zetaris test.

## Post-change verification

| Check | Command | Result / scope |
| --- | --- | --- |
| Full Python suite | `PYTHON_DOTENV_DISABLED=true .venv/bin/python -m pytest -q` | 128 passed, 1 skipped in 114.70s. The skip was the live Zetaris acceptance gate. |
| Auth, Zetaris, webhook/startup focused suite | `PYTHON_DOTENV_DISABLED=true .venv/bin/python -m pytest tests/test_agentboxd_api.py tests/test_auth_rbac.py tests/test_zetaris.py tests/test_api.py -q` | 50 passed, 1 skipped in 20.28s. Covers cookie session/CSRF/RBAC, startup mounting, malformed/outage Zetaris responses, and server-configured webhook tenancy. |
| Evaluation/auth/provider regression chain | `PYTHON_DOTENV_DISABLED=true .venv/bin/python -m pytest tests/test_evaluation.py tests/test_agentboxd_api.py tests/test_zetaris.py tests/test_auth_rbac.py -q` | Completed in the final chained local verification; output capture was unavailable, so this is not counted as a release-approval result. The separately recorded focused suite remains the authoritative counted result. |
| Frontend unit | `npm --prefix frontend test -- --reporter=dot` | 1 file, 4 tests passed in 7.74s. |
| Frontend typecheck/build | `npm --prefix frontend run build` | passed in 5.17s; Vite emitted generated `dist/` output only. |
| Offline benchmark | `PYTHON_DOTENV_DISABLED=true .venv/bin/python -m evaluation.runner` | Generated `.artifacts/latest_report.*`: precision 1.0000, recall 0.8667, F1 0.9286, TP 65, FP 0, TN 50, FN 10. This is an offline demo-heuristic benchmark, not live-provider performance. |
| Compose validation | `docker compose config --quiet` | passed. |
| Container build and smoke | `docker build -t veriforge-test .`; `docker run ... veriforge-test` | passed. `/ready` returned ready; `/api/v1/integrations/status` reported Zetaris `not_configured`; runtime UID was 10001. The temporary container was removed after the check. |
| Python dependency audit | `.venv/bin/python -m pip_audit -r requirements.txt` | No known vulnerabilities found. |
| Frontend production dependency audit | `npm --prefix frontend audit --omit=dev --audit-level=high` | 0 vulnerabilities found. |
| High-confidence secret-format scan | `rg -n "AKIA…|ghp_…|sk-…|PRIVATE KEY"` over tracked source | No matches. CI enforces the same high-confidence patterns. |
| Generated-file hygiene | `git ls-files -ci --exclude-standard` | 0 tracked ignored/generated files. |
| Whitespace hygiene | `git diff --check` | passed. |

## Deliberately gated or not claimed

- **Live Zetaris**: not run. It requires `RUN_LIVE_ZETARIS_TESTS=1`, a
  participant-provided UI URL, dedicated read-only identity, approved datasource
  mapping, and known test hostname. No platform `.env` was read or copied.
- **Live Featherless**: not run. Verification used deterministic demo mode.
- **Public deployment / hosted CI / security audit**: not performed or claimed.
- CI also runs dependency/secret scan commands; no hosted-CI result is claimed.

## Reproduction sequence

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt
npm --prefix frontend ci
PYTHON_DOTENV_DISABLED=true .venv/bin/python -m pytest -q
npm --prefix frontend test -- --reporter=dot
npm --prefix frontend run build
PYTHON_DOTENV_DISABLED=true .venv/bin/python -m evaluation.runner
docker compose config --quiet
```

Run the live test only after the approved Zetaris prerequisites have been
provided; its result is a release blocker, not an optional demonstration.
