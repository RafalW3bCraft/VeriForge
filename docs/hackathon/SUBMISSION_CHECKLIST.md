# Submission Checklist

Deadline: 2026-10-27 23:45 UTC. Status as of 2026-10-26.

## Gates (from brief §10)

1. [x] Project starts with documented commands — verified: local uvicorn and
   `docker build`/`docker run` both serve /ready and a full investigation.
2. [x] Existing functionality intact — 63/63 baseline tests still pass;
   benchmark identical to baseline re-run (F1 0.929); frontend test + build pass.
3. [~] Sponsor integrations demonstrably operational:
   - H-MEM: YES — in-process, tested (23 contract tests), demonstrated live
     (cross-investigation memory reuse in Docker).
   - Zetaris: IMPLEMENTED + unit-tested; live demo BLOCKED on
     `ZETARIS_BASE_URL` (participant instance URL) — reported honestly as
     not_configured; nothing mocked presented as live.
4. [x] Evidence-backed conclusions — typed evidence, hypotheses, provenance,
   verification-gated risk.
5. [x] Security/regression tests pass — injection screening, auth, error
   sanitization, outage handling, isolation: all green.
6. [x] New-work disclosure accurate — PRE_EXISTING_WORK_DISCLOSURE.md +
   NEW_WORK_CHANGELOG.md + git diff ff32c6c..HEAD.
7. [x] Demo reproducible — SETUP_AND_DEMO.md verified command-by-command.
8. [x] Submission artifacts complete — all 10 required docs present in
   docs/hackathon/.

## Compliance

- [x] Baseline commit recorded (ff32c6c); no pre-existing code claimed as new.
- [x] Git history preserved.
- [x] Zetaris + Meterless are working runtime dependencies (H-MEM live;
  Zetaris runtime-active with truthful status).
- [x] No mocked sponsor calls presented as live evidence.
- [x] Secrets out of Git: .env git-ignored; `.hmem/` git-ignored; no
  credentials in code, tests, snapshots or frontend bundle.
- [x] Cursor usage recorded (not used); NVIDIA not used (recorded).
- [x] Nothing submitted externally without user approval.

## Remaining actions (owner: user)

1. Provide Zetaris instance URL (`ZETARIS_BASE_URL`, `ZETARIS_ORG_ID`) →
   run the live acceptance gate (one command, in SETUP_AND_DEMO.md).
2. Approve final submission (explicit approval required before any external
   submission).
3. Optional: record the 3-minute demo per DEMO_SCRIPT_3_MINUTES.md.
