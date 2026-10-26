# VeriForge — Project Description

VeriForge investigates suspicious messages, emails and URLs the way a careful
analyst would: it extracts what the message claims, gathers evidence from
outside the message itself, checks its own reasoning, and only then decides a
risk verdict. It can explain **why** — every verdict links back to typed
evidence, external corroboration, and a memory of what it learned before.

## Problem

People receive phishing and social-engineering messages that look plausible
because the claims inside them can't be checked from the text alone. Most
AI-based detectors answer with a label and a probability — a black box the
user must trust blindly, and one that contradicts itself from one message to
the next because it remembers nothing.

## What VeriForge does

1. Extracts claims and observable indicators (URLs, domains, sender addresses,
   credential and financial requests) from the submitted content.
2. Forms explicit, falsifiable hypotheses about the message.
3. Correlates indicators against external threat data through **Zetaris**,
   using bounded read-only SQL queries — the message text never becomes SQL.
4. Retrieves trusted context from its own **Meterless H-MEM** memory: what
   previous investigations concluded about these indicators, with provenance.
5. Runs four specialist agents (identity, infrastructure, social engineering,
   verification) over the assembled evidence.
6. Verifies which findings are actually supported, which contradict each
   other, and which are unsupported — unsupported claims are named, not hidden.
7. Computes the final risk deterministically in Python, outside the LLM. A
   critical signal cannot force a top verdict unless verification supports it.
8. Explains the result: verdict, confidence, evidence strength, hypotheses
   and their outcomes, external evidence with source and retrieval time, and
   the memory it reused — including which earlier investigation it came from.
9. Remembers trusted conclusions for the next investigation, per tenant, with
   an audit trail.

If a sponsor system or model provider is unavailable, VeriForge reports the
investigation as incomplete and caps the verdict rather than inventing an
answer.

## Status

Prototype, not a production security service. Verdicts support — never
replace — independent verification.
