# Demo Script — 3 minutes

Setup before recording: app running at localhost:8000 (Docker or local),
DEMO_MODE=true, browser on the dashboard.

## 0:00–0:20 — The problem

"Phishing works because you can't check a message's claims from the text
alone. VeriForge investigates messages like an analyst: it gathers evidence
outside the message, checks its own reasoning, and explains why — with proof."
Show the dashboard; point at the Zetaris and H-MEM status badges.

## 0:20–1:00 — Investigation one

Paste the phishing scenario (account suspension, credential link to
`phish-site-one.example`). Click Analyze.

Narrate over the result:
- Verdict CRITICAL with risk score, and — distinctly — confidence and
  evidence strength.
- Hypotheses panel: "domain associated with known threats", "credential
  harvesting" — marked supported/unverified individually.
- The pipeline steps and integration status are part of the response.

## 1:00–1:40 — Memory in action (H-MEM)

Analyze a second, differently-worded message about the SAME domain.

Point at "Memory context (H-MEM)":
- "Investigation <id>: CRITICAL … retrieved because it matched on
  entity/keyword; source veriforge:investigation; from prior investigation
  5673d389."
- "The agent remembered the first verdict — with provenance, a retrieval
  reason, and a relevance score. Tenant isolation means this memory never
  leaks to another tenant."

## 1:40–2:20 — Evidence and verification depth

Open the saved analysis from History:
- Findings mapped to supporting evidence; unsupported claims named explicitly.
- Contradictions panel: nothing hidden.
- Explain: "Risk is computed in Python, not by the LLM. A critical signal
  can't force a top verdict unless verification actually supports it."

## 2:20–2:50 — Honest failure + Zetaris

Point at `zetaris: not_configured` badge: "VeriForge never fakes its
integrations. Zetaris correlation is implemented against the documented SQL
proxy — when the instance URL is provisioned, this badge turns green and
indicators are corroborated against live threat data. Today it reports its
real status." Show `/api/v1/integrations/status` JSON.

If a Zetaris instance IS available at demo time: run the live lookup and show
the external evidence panel with source, record id and retrieval time.

## 2:50–3:00 — Close

"Evidence in, memory across investigations, verdicts that explain why — and
silence instead of invention when something is down. VeriForge."
