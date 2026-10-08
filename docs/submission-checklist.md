# Submission checklist

This checklist is intended for the final ForgeHacks submission and should be used as a verification pass before sharing a build or a demo link.

## 1. Proof of working system
- [ ] Backend starts locally without errors.
- [ ] Health endpoint returns a 200 response.
- [ ] Ready endpoint returns a 200 response when the database is available.
- [ ] Analysis endpoint accepts valid messages and persists a result.
- [ ] Signed Agentboxd webhook flow is tested with valid and invalid signatures.
- [ ] Benchmark pipeline runs offline and produces a deterministic score.

## 2. Security and validation gates
- [ ] `DEMO_MODE` is used only for local offline validation.
- [ ] Production credentials are kept in `.env` and never committed to source control.
- [ ] Request size limits and rate limiting are enabled.
- [ ] Sensitive errors are not exposed to clients.
- [ ] Timestamps and signatures are validated before webhook processing.

## 3. Demo and screenshots
- [ ] Capture a clean login or launch screen if the frontend is used.
- [ ] Capture the analysis result for a malicious email or suspicious message.
- [ ] Capture the evidence graph or extracted indicators view.
- [ ] Capture a benchmark or report output showing offline deterministic results.
- [ ] Record a short 2–4 minute demo script and speaking notes.

## 4. Documentation readiness
- [ ] README reflects the current implementation state accurately.
- [ ] Threat model and architecture notes are up to date.
- [ ] Agentboxd and Featherless integration docs are current.
- [ ] Benchmark or evaluation notes describe the offline validation path.

## 5. Final repository hygiene
- [ ] No secrets, tokens, or API keys are present in tracked files.
- [ ] Test suite passes: `python -m pytest -q`.
- [ ] Docker and Compose workflows build successfully if used for demonstration.
- [ ] There are no unsupported claims about production readiness or model certainty.

## 6. Final demo sequence
1. Launch the backend or Docker container.
2. Hit the health and ready endpoints.
3. Submit a suspicious message or sample email.
4. Show extracted evidence and the final risk decision.
5. Show the benchmark output to demonstrate the deterministic pipeline works offline.
6. Summarize the product as evidence-first detection, not a fully autonomous security verdict engine.

## 7. Sign-off
- [ ] The project is ready for handoff.
- [ ] The demo narrative matches the verified repo state.
- [ ] The final submission avoids unsupported performance or safety claims.
