# Slide Deck Content

## 1. Title
VeriForge — the agent that can explain why.
Evidence-grounded phishing investigation with Zetaris correlation and
Meterless H-MEM memory. Track 2, GenAI.Works Open Agent Hackathon 2026.

## 2. Problem
- Phishing succeeds because message claims can't be checked from the text.
- AI detectors answer with a label + probability: a black box.
- Stateless agents contradict themselves message to message.
- Users need reasons they can verify, not verdicts they must trust.

## 3. Target users
- Security-conscious individuals triaging suspicious messages.
- SOC analysts who need auditable first-pass triage.
- Support teams handling reported-phishing inboxes.

## 4. Agent architecture
[Diagram: pipeline v2 — screen → extract → hypothesize → correlate (Zetaris)
→ recall (H-MEM) → specialists → verify → deterministic risk → explain →
persist]
- LLM proposes findings; Python decides risk.
- Critical signals gated on verification support.
- Explicit hypotheses with supported/contradicted/unverified outcomes.

## 5. Technical stack
- FastAPI + Pydantic backend; SQLite persistence.
- React 19 + Vite + Tailwind frontend.
- Featherless LLM for specialist reasoning; deterministic risk engine.
- Docker single-image deployment.
- 119 Python tests + frontend tests + 150-sample offline benchmark.

## 6. Sponsor integration
- **Zetaris**: read-only SQL via documented UI proxy; typed evidence with
  source, record id, query reference, retrieval time; injection-proof
  templates; explicit unavailable/failed status.
- **Meterless H-MEM**: canonical memory record, hybrid retrieval formula with
  trace, append-only trust ledger, conflict detection, high-trust floor,
  tenant/investigation isolation — implemented per official AGENTS.md spec.

## 7. Distinctive contributions
- Memory reuse with attribution: second investigation cites the first.
- Verification-gated risk: unverified critical signals can't force verdicts.
- Honest failure: incomplete investigations are reported and capped, never
  invented.
- Benchmark integrity: decision coverage and abstentions reported explicitly.

## 8. Screenshots
1. Dashboard with integration badges.
2. Verdict panel: score vs confidence vs evidence strength.
3. Memory trace citing a prior investigation.
4. Hypotheses panel with per-hypothesis outcomes.
5. Verification panel: agreements, contradictions, unsupported claims.

## 9. Measurable results
- 119/120 tests pass (1 skipped: live Zetaris, env-gated).
- Offline benchmark: precision 1.0, recall 0.93, F1 0.929, zero false
  positives on 50 benign samples — identical to baseline, no regressions.
- Docker image builds and serves a full investigation end-to-end.

## 10. Future enhancements
- Live Zetaris datasets once instance URL is provisioned (code path ready).
- H-MEM dreaming/sleep cycles (spec-optional, currently documented as out).
- Embedding-backed semantic retrieval (replacing model-free fallback).
- SQLite backing for long-term memory tier.
