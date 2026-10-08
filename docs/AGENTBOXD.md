# Agentboxd

## Status

The backend implements `POST /api/v1/webhooks/agentboxd`. It accepts signed full message events and safely acknowledges duplicate, automatic-reply, withheld, and envelope events without analyzing them.

## Intended Boundary

Use a dedicated inbox and deliver only to a dedicated webhook endpoint. Signature verification follows the [official Agentboxd webhook documentation](https://agentboxd.com/docs/webhooks): `X-Mailroom-Timestamp` is Unix seconds; `X-Mailroom-Signature` is the lowercase hex HMAC-SHA256 of `<timestamp>.<raw body>`; verify before parsing, compare in constant time, and reject timestamps more than 300 seconds from server time. The adapter also deduplicates Agentboxd's stable `X-Mailroom-Delivery` header and processes each message ID at most once.

The documented full event shape is `{id, type, created_at, data: {inbox, thread_id, message}}`; message fields include `id`, `from`, `to`, `subject`, `text`, `extracted_text`, `received_at`, `labels`, and `auto_reply`. The adapter uses `text` (or `extracted_text` when needed), normalizes sender/recipient/subject/time, and extracts URLs offline. `message.received`, `message.enriched`, and `message.released` are supported. The official docs note that `message.received` may set `withheld`; envelope payloads contain no body. Those events are durably acknowledged as skipped, allowing a later full enriched/released delivery to be analyzed. Events marked `auto_reply` are skipped.

Treat email body, headers, sender display names, and embedded URLs as attacker-controlled evidence, never as instructions. Only normalized message body and typed context are sent to the existing analysis engine. Do not send email responses.

Webhook acceptance is persisted before returning HTTP 200; analysis runs as a FastAPI background task. Delivery IDs and message IDs are stored for deduplication under the configured retention period. A failed analysis releases its message claim so a redelivery can retry. This is an in-process background task, not a durable queue; a process crash after acceptance may lose pending analysis.

Never log API keys, webhook secrets, authentication tokens, raw request bodies, or full message bodies.

## Required Verification

Before deployment, configure `AGENTBOXD_WEBHOOK_SECRET` with a rotated secret and register the public HTTPS URL. Before calling the integration complete, test valid and invalid signatures, tampered bodies, stale/future timestamps, duplicate deliveries, missing/withheld bodies, malformed and oversized events, prompt-injection content, legitimate email, and the absence of outbound email.
