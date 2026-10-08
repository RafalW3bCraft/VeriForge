# VeriForge Architecture

## Current Prototype

The current application is a small FastAPI service. `apps/api/main.py` defines `GET /health` and `POST /api/v1/analyze`; `engine.py` extracts indicators, invokes three specialist agents, invokes a verifier, calculates risk, and returns the result. Demo agents use local heuristics. Live agents call the OpenAI-compatible Featherless API through `agents/common.py`.

The response now includes an evidence-derived graph containing extracted claim/evidence nodes, specialist finding nodes, agents that produced findings, and the risk decision. Edges encode containment, support, detection, and contribution. The frontend graph view and persistent analysis history are not implemented yet.

The backend persists typed analysis results, findings, extracted evidence, and Agentboxd event metadata in SQLite, and exposes analysis-history list/detail endpoints. It does not store a dedicated raw-input field. There is no frontend or deployment configuration in the current repository. Webhook analysis uses FastAPI background tasks, not a durable job queue.

## Target Data Flow

Input → API validation → normalization → claim extraction → evidence collection → identity, infrastructure, and social-engineering analysis → evidence graph → cross-agent verification → deterministic risk aggregation → explainable decision → persistence.

Each stage should exchange typed, validated data. Claims and evidence should retain source/provenance information. The evidence graph should contain only entities and relationships supported by input or collected evidence; the execution workflow should remain a separate concept.

The verifier should see original structured evidence and independent agent findings so it can assess support, contradiction, and missing evidence. The risk engine should consume validated outputs, produce a deterministic score outside the LLM, and report confidence and evidence strength separately.

## Integration Boundaries

- Featherless: one centralized client; analyzed content is untrusted user data; validate structured outputs before use.
- Agentboxd: isolated signed webhook adapter; verify raw bytes and the documented timestamp tolerance before parsing; durably deduplicate delivery/message IDs; normalize events; never send replies.
- SQLite: stores analyses, findings, and evidence with a configurable retention period, plus webhook event/delivery/message IDs and minimal metadata for dedupe and history.
- Frontend: planned React/TypeScript client that displays verdict, evidence, graph, and safe next action without holding provider secrets.

## Network Safety

URL extraction is currently offline and must remain so unless a constrained inspection client is designed and tested. Never fetch arbitrary URLs from user content. Any future network evidence collector needs SSRF protections for private, loopback, link-local, metadata, redirected, and rebinding destinations.