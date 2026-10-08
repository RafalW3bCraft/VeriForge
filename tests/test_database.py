import asyncio
from datetime import datetime, timedelta, timezone

from database import AnalysisRecord, Database, EvidenceRecord, FindingRecord
from engine import analyze


def test_analysis_round_trips_without_storing_original_body(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    database = Database(f"sqlite:///{tmp_path / 'veriforge-test.db'}")
    original_body = "URGENT: enter password at https://example.zip"
    response = asyncio.run(analyze(original_body))

    database.save_analysis(response)
    restored = database.get_analysis(response.analysis_id)
    summaries = database.list_analyses()

    assert restored.model_dump(mode="json") == response.model_dump(mode="json")
    assert summaries[0].analysis_id == response.analysis_id
    with database._session_factory() as session:
        stored_analysis = session.get(AnalysisRecord, response.analysis_id)
        assert stored_analysis is not None
        assert original_body not in str(stored_analysis.result_json)
        assert session.query(EvidenceRecord).filter_by(analysis_id=response.analysis_id).count() > 0
        assert session.query(FindingRecord).filter_by(analysis_id=response.analysis_id).count() > 0


def test_retention_prunes_expired_analysis_and_child_rows(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    database = Database(f"sqlite:///{tmp_path / 'retention-test.db'}")
    response = asyncio.run(analyze("Urgent password request at https://example.zip"))
    database.save_analysis(response)
    with database._session_factory.begin() as session:
        row = session.get(AnalysisRecord, response.analysis_id)
        row.created_at = datetime.now(timezone.utc) - timedelta(days=40)

    assert database.prune_expired(retention_days=30) == 1
    assert database.get_analysis(response.analysis_id) is None
    with database._session_factory() as session:
        assert session.query(EvidenceRecord).filter_by(analysis_id=response.analysis_id).count() == 0
        assert session.query(FindingRecord).filter_by(analysis_id=response.analysis_id).count() == 0


def test_webhook_deduplicates_delivery_and_message_ids(tmp_path):
    database = Database(f"sqlite:///{tmp_path / 'webhook-dedupe.db'}")
    accepted = database.accept_webhook_event(
        event_id="event-1",
        delivery_id="delivery-1",
        message_id="message-1",
        event_type="message.received",
        state="accepted",
        claim_message=True,
    )
    duplicate_delivery = database.accept_webhook_event(
        event_id="event-1",
        delivery_id="delivery-1",
        message_id="message-1",
        event_type="message.received",
        state="accepted",
        claim_message=True,
    )
    duplicate_message = database.accept_webhook_event(
        event_id="event-2",
        delivery_id="delivery-2",
        message_id="message-1",
        event_type="message.enriched",
        state="accepted",
        claim_message=True,
    )

    assert accepted == "accepted"
    assert duplicate_delivery == "duplicate_delivery"
    assert duplicate_message == "duplicate_message"


def test_withheld_webhook_does_not_claim_message_id(tmp_path):
    database = Database(f"sqlite:///{tmp_path / 'webhook-withheld.db'}")
    withheld = database.accept_webhook_event(
        event_id="event-1",
        delivery_id="delivery-1",
        message_id="message-1",
        event_type="message.received",
        state="withheld",
        claim_message=False,
    )
    enriched = database.accept_webhook_event(
        event_id="event-2",
        delivery_id="delivery-2",
        message_id="message-1",
        event_type="message.enriched",
        state="accepted",
        claim_message=True,
    )

    assert withheld == "withheld"
    assert enriched == "accepted"


def test_failed_webhook_analysis_can_be_retried(tmp_path):
    database = Database(f"sqlite:///{tmp_path / 'webhook-retry.db'}")
    first = database.accept_webhook_event(
        event_id="event-1",
        delivery_id="delivery-1",
        message_id="message-1",
        event_type="message.received",
        state="accepted",
        claim_message=True,
    )
    database.update_webhook_event("event-1", "failed")
    retry = database.accept_webhook_event(
        event_id="event-1",
        delivery_id="delivery-1",
        message_id="message-1",
        event_type="message.received",
        state="accepted",
        claim_message=True,
    )

    assert first == "accepted"
    assert retry == "accepted"