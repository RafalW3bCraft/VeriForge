# Challenge Alignment — Track 2: The Agent That Can Explain Why

Event: GenAI.Works Open Agent Hackathon 2026
Submission deadline: 2026-10-27 23:45 UTC
Baseline (pre-existing work): commit `ff32c6cdd5e7762844dda3e80ac8f96e63db681b`

## How VeriForge answers the track

| Track expectation | VeriForge mechanism | Where |
| --- | --- | --- |
| Agent explains WHY, not just a label | Every finding carries typed evidence references; hypotheses show supported / contradicted / unverified outcomes | `models.py` (Finding.evidence_ids, Hypothesis), `engine.py` |
| Evidence-grounded reasoning | Indicators are corroborated externally via Zetaris before they can lift the verdict | `evidence/external.py` |
| Memory with provenance | H-MEM records carry source, provenance label, confidence, originating investigation; retrieval returns a trace explaining why each memory was selected | `hmem/` |
| Deterministic, inspectable decisions | Risk is computed in Python, never by the LLM; critical signals are gated on verification support | `evidence/risk.py` |
| Honest failure | Unavailable integrations produce explicit status and an incomplete verdict, never a fabricated one | `engine.py`, `integrations/zetaris/client.py` |
| Contradiction awareness | H-MEM conflict detection flags contradictory facts; superseded facts are penalized, never silently deleted | `hmem/conflicts.py` |

## Sponsor technology (required)

- **Zetaris**: runtime dependency for external threat-indicator correlation.
  Implemented against the documented HTTP/SQL route (UI proxy) from
  `zetaris/getting-started`. See SPONSOR_TECH_EXPLANATION.md and
  INTEGRATION_STATUS.md. Live acceptance gate currently blocked on the
  participant's Zetaris instance URL (`ZETARIS_BASE_URL`); unit tests and
  outage behavior are fully tested.
- **Meterless H-MEM**: implemented in-process following the official
  `engines/hmem/AGENTS.md` spec (the repo explicitly directs implementing the
  contracts in your own stack). Conformance-style tests cover the canonical
  record, retrieval formula, feedback deltas, trust floor, supersede
  semantics and isolation rules. Dreaming and sleep cycles are documented as
  not implemented (spec-optional).

## Optional technology

- Cursor: not used.
- NVIDIA: not used; no meaningful contribution for this project within the deadline.
