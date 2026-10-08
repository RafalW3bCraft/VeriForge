import hashlib
import hmac
import logging
import re
import time
from email.utils import parseaddr
from typing import Any

from pydantic import ValidationError

from database import PersistenceError, get_database
from engine import analyze
from evidence.extractor import extract_claims
from models import AnalysisResponse, NormalizedEmail, WebhookEvent

SIGNATURE_TOLERANCE_SECONDS = 300
MAIL_EVENTS = {"message.received", "message.enriched", "message.released"}
logger = logging.getLogger(__name__)


class AgentboxdPayloadError(ValueError):
    pass


def verify_webhook_signature(
    signature: str | None,
    timestamp: str | None,
    raw_body: bytes,
    secret: str,
    *,
    now: float | None = None,
) -> bool:
    if (
        not signature
        or not re.fullmatch(r"[0-9a-f]{64}", signature)
        or not timestamp
        or not secret
    ):
        return False
    if not re.fullmatch(r"[0-9]+", timestamp):
        return False
    timestamp_seconds = int(timestamp)
    current_seconds = time.time() if now is None else now
    if abs(current_seconds - timestamp_seconds) > SIGNATURE_TOLERANCE_SECONDS:
        return False
    signed_payload = timestamp.encode("ascii") + b"." + raw_body
    expected = hmac.new(
        secret.encode("utf-8"), signed_payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


def parse_webhook_event(raw_body: bytes) -> WebhookEvent:
    try:
        return WebhookEvent.model_validate_json(raw_body)
    except ValidationError as exc:
        raise AgentboxdPayloadError("Invalid webhook event payload") from exc


def normalize_message_event(event: WebhookEvent) -> NormalizedEmail:
    message = event.data.get("message")
    if not isinstance(message, dict):
        raise AgentboxdPayloadError("Full message payload is required")
    body = message.get("text") or message.get("extracted_text")
    if not isinstance(body, str) or not body.strip():
        raise AgentboxdPayloadError("Message body is missing")
    raw_sender = message.get("from")
    if not isinstance(raw_sender, str) or not raw_sender.strip():
        raise AgentboxdPayloadError("Message sender is missing")
    sender = parseaddr(raw_sender)[1] or raw_sender.strip()
    raw_recipients = message.get("to")
    recipient = (
        raw_recipients[0]
        if isinstance(raw_recipients, list) and raw_recipients
        else raw_recipients
    )
    if not isinstance(recipient, str):
        recipient = None
    message_id = message.get("id")
    if not isinstance(message_id, str) or not message_id:
        raise AgentboxdPayloadError("Message id is missing")
    subject = message.get("subject")
    if not isinstance(subject, str):
        subject = ""
    received_at = message.get("received_at") or event.created_at
    try:
        normalized = NormalizedEmail(
            message_id=message_id,
            sender=sender,
            recipient=recipient,
            subject=subject[:998],
            body=body,
            received_at=received_at,
            urls=extract_claims(body).urls,
        )
    except ValidationError as exc:
        raise AgentboxdPayloadError("Message payload failed validation") from exc
    return normalized


def get_message_metadata(event: WebhookEvent) -> dict[str, Any]:
    message = event.data.get("message")
    if not isinstance(message, dict):
        return {}
    return {
        key: message[key]
        for key in ("labels", "channel", "type", "auto_reply", "screening", "ai", "analysis")
        if key in message
    }


async def process_normalized_message(
    event_id: str, normalized: NormalizedEmail, metadata: dict[str, Any]
) -> AnalysisResponse | None:
    database = get_database()
    context = {
        "source": "agentboxd",
        "message_id": normalized.message_id,
        "sender": normalized.sender,
        "recipient": normalized.recipient,
        "subject": normalized.subject,
        "received_at": (
            normalized.received_at.isoformat()
            if normalized.received_at is not None
            else None
        ),
        "agentboxd": metadata,
    }
    try:
        result = await analyze(normalized.body, "email", context)
        database.save_analysis(result)
        database.update_webhook_event(event_id, "processed", result.analysis_id)
        return result
    except Exception as exc:
        try:
            database.update_webhook_event(event_id, "failed")
        except PersistenceError:
            pass
        logger.error(
            "Agentboxd message analysis failed",
            extra={"event_id": event_id, "error_type": type(exc).__name__},
        )
        return None