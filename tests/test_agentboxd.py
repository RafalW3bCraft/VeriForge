import hashlib
import hmac
import json

import pytest

from integrations.agentboxd import (
    AgentboxdPayloadError,
    normalize_message_event,
    parse_webhook_event,
    verify_webhook_signature,
)


def signed(raw_body: bytes, timestamp: str, secret: str) -> str:
    signed_payload = timestamp.encode("ascii") + b"." + raw_body
    return hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()


def event_payload(body="Please review https://example.zip"):
    return {
        "id": "event-1",
        "type": "message.received",
        "created_at": "2026-10-08T12:00:00Z",
        "data": {
            "inbox": {"id": "inbox-1", "address": "veriforge@example.test"},
            "thread_id": "thread-1",
            "message": {
                "id": "message-1",
                "from": "Dana Example <dana@example.test>",
                "to": ["veriforge@example.test"],
                "subject": "Review this notice",
                "text": body,
                "extracted_text": body,
                "received_at": "2026-10-08T11:59:00Z",
                "auto_reply": False,
                "labels": ["inbound"],
            },
        },
    }


def test_signature_uses_timestamp_and_exact_raw_body():
    secret = "unit-test-secret"
    timestamp = "1000"
    raw_body = b'{"id":"evt-1","type":"message.received","data":{}}'
    signature = signed(raw_body, timestamp, secret)

    assert verify_webhook_signature(signature, timestamp, raw_body, secret, now=1000)
    assert not verify_webhook_signature(
        signature, timestamp, raw_body + b" ", secret, now=1000
    )
    assert not verify_webhook_signature(signature, timestamp, raw_body, "wrong", now=1000)


@pytest.mark.parametrize("offset", [-301, 301])
def test_signature_rejects_timestamps_outside_documented_tolerance(offset):
    timestamp = str(1000 + offset)
    raw_body = b"{}"
    signature = signed(raw_body, timestamp, "unit-test-secret")

    assert not verify_webhook_signature(
        signature, timestamp, raw_body, "unit-test-secret", now=1000
    )


def test_signature_rejects_missing_or_malformed_headers():
    assert not verify_webhook_signature(None, "1000", b"{}", "secret", now=1000)
    assert not verify_webhook_signature("abc", "not-a-time", b"{}", "secret", now=1000)
    assert not verify_webhook_signature("A" * 64, "1000", b"{}", "secret", now=1000)


def test_normalize_full_message_payload_extracts_sender_subject_body_urls():
    raw_body = json.dumps(event_payload()).encode()
    event = parse_webhook_event(raw_body)

    normalized = normalize_message_event(event)

    assert normalized.message_id == "message-1"
    assert normalized.sender == "dana@example.test"
    assert normalized.recipient == "veriforge@example.test"
    assert normalized.subject == "Review this notice"
    assert normalized.body == "Please review https://example.zip"
    assert normalized.urls == ["https://example.zip"]


def test_missing_body_is_rejected_for_normalization():
    payload = event_payload()
    payload["data"]["message"].pop("text")
    payload["data"]["message"].pop("extracted_text")

    with pytest.raises(AgentboxdPayloadError, match="body is missing"):
        normalize_message_event(parse_webhook_event(json.dumps(payload).encode()))