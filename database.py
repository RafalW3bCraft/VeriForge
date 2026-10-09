from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    JSON,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    delete,
    select,
    update,
    or_,
)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from config import get_settings
from models import AnalysisResponse, AnalysisSummary


class Base(DeclarativeBase):
    pass


class AnalysisRecord(Base):
    __tablename__ = "analyses"

    analysis_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    input_type: Mapped[str] = mapped_column(String(20))
    score: Mapped[float] = mapped_column(Float)
    verdict: Mapped[str] = mapped_column(String(20), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    evidence_strength: Mapped[float] = mapped_column(Float)
    summary: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str] = mapped_column(Text)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON)


class FindingRecord(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("analyses.analysis_id", ondelete="CASCADE"), index=True
    )
    agent: Mapped[str] = mapped_column(String(40))
    finding: Mapped[str] = mapped_column(String(200))
    severity: Mapped[str] = mapped_column(String(20))
    evidence: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(80))
    confidence: Mapped[float] = mapped_column(Float)


class EvidenceRecord(Base):
    __tablename__ = "evidence"

    evidence_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("analyses.analysis_id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(40))
    value: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(80))
    snippet: Mapped[str | None] = mapped_column(String(240))
    observed: Mapped[bool] = mapped_column(default=True)


class WebhookEventRecord(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (UniqueConstraint("delivery_id", name="uq_webhook_delivery_id"),)

    event_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    delivery_id: Mapped[str | None] = mapped_column(String(100), index=True)
    message_id: Mapped[str | None] = mapped_column(String(100), index=True)
    event_type: Mapped[str] = mapped_column(String(80))
    state: Mapped[str] = mapped_column(String(20), default="accepted")
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    sender: Mapped[str | None] = mapped_column(String(320))
    recipient: Mapped[str | None] = mapped_column(String(320))
    subject: Mapped[str | None] = mapped_column(String(998))
    analysis_id: Mapped[str | None] = mapped_column(
        ForeignKey("analyses.analysis_id", ondelete="SET NULL")
    )


class WebhookMessageClaim(Base):
    __tablename__ = "webhook_message_claims"

    message_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(100), unique=True)
    claimed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class PersistenceError(RuntimeError):
    pass


class Database:
    def __init__(self, url: str):
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.engine = create_engine(url, connect_args=connect_args)
        self._session_factory = sessionmaker(self.engine, expire_on_commit=False)
        try:
            Base.metadata.create_all(self.engine)
        except SQLAlchemyError as exc:
            raise PersistenceError("Database initialization failed") from exc
        self.prune_expired()

    def prune_expired(self, retention_days: int | None = None) -> int:
        days = retention_days or get_settings().retention_days
        if days < 1:
            raise ValueError("retention_days must be positive")
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        try:
            with self._session_factory.begin() as session:
                expired_ids = session.scalars(
                    select(AnalysisRecord.analysis_id).where(
                        AnalysisRecord.created_at < cutoff
                    )
                ).all()
                if expired_ids:
                    session.execute(
                        delete(FindingRecord).where(
                            FindingRecord.analysis_id.in_(expired_ids)
                        )
                    )
                    session.execute(
                        delete(EvidenceRecord).where(
                            EvidenceRecord.analysis_id.in_(expired_ids)
                        )
                    )
                    session.execute(
                        update(WebhookEventRecord)
                        .where(WebhookEventRecord.analysis_id.in_(expired_ids))
                        .values(analysis_id=None)
                    )
                    session.execute(
                        delete(AnalysisRecord).where(
                            AnalysisRecord.analysis_id.in_(expired_ids)
                        )
                    )
                session.execute(
                    delete(WebhookEventRecord).where(
                        WebhookEventRecord.received_at < cutoff
                    )
                )
                session.execute(
                    delete(WebhookMessageClaim).where(
                        WebhookMessageClaim.claimed_at < cutoff
                    )
                )
                return len(expired_ids)
        except SQLAlchemyError as exc:
            raise PersistenceError("Retention cleanup failed") from exc

    def save_analysis(self, response: AnalysisResponse) -> None:
        payload = response.model_dump(mode="json")
        try:
            with self._session_factory.begin() as session:
                session.add(AnalysisRecord(
                    analysis_id=response.analysis_id,
                    created_at=response.created_at,
                    input_type=response.input_type,
                    score=response.score,
                    verdict=response.verdict,
                    confidence=response.confidence,
                    evidence_strength=response.risk_decision.evidence_strength,
                    summary=response.summary,
                    recommended_action=response.recommended_action,
                    result_json=payload,
                ))
                for evidence in response.extraction.evidence:
                    session.add(EvidenceRecord(
                        evidence_id=f"{response.analysis_id}:{evidence.id}",
                        analysis_id=response.analysis_id,
                        kind=evidence.kind,
                        value=evidence.value,
                        source=evidence.source,
                        snippet=evidence.snippet,
                        observed=evidence.observed,
                    ))
                for agent_name, agent in response.agents.model_dump().items():
                    for finding in agent["findings"]:
                        session.add(FindingRecord(
                            id=str(uuid4()),
                            analysis_id=response.analysis_id,
                            agent=agent_name,
                            finding=finding["finding"],
                            severity=finding["severity"],
                            evidence=finding["evidence"],
                            source=finding["source"],
                            confidence=finding["confidence"],
                        ))
        except SQLAlchemyError as exc:
            raise PersistenceError("Analysis persistence failed") from exc

    def list_analyses(self, limit: int = 20) -> list[AnalysisSummary]:
        try:
            with self._session_factory() as session:
                rows = session.scalars(
                    select(AnalysisRecord)
                    .order_by(AnalysisRecord.created_at.desc())
                    .limit(limit)
                ).all()
                return [
                    AnalysisSummary(
                        analysis_id=row.analysis_id,
                        created_at=row.created_at,
                        input_type=row.input_type,
                        score=row.score,
                        verdict=row.verdict,
                        summary=row.summary,
                    )
                    for row in rows
                ]
        except SQLAlchemyError as exc:
            raise PersistenceError("Analysis lookup failed") from exc

    def get_analysis(self, analysis_id: str) -> AnalysisResponse | None:
        try:
            with self._session_factory() as session:
                row = session.get(AnalysisRecord, analysis_id)
                if row is None:
                    return None
                return AnalysisResponse.model_validate(row.result_json)
        except SQLAlchemyError as exc:
            raise PersistenceError("Analysis lookup failed") from exc

    def accept_webhook_event(
        self,
        *,
        event_id: str,
        delivery_id: str | None,
        message_id: str | None,
        event_type: str,
        state: str,
        sender: str | None = None,
        recipient: str | None = None,
        subject: str | None = None,
        claim_message: bool = False,
    ) -> str:
        try:
            with self._session_factory.begin() as session:
                existing_event = session.scalar(
                    select(WebhookEventRecord).where(
                        or_(
                            WebhookEventRecord.event_id == event_id,
                            WebhookEventRecord.delivery_id == delivery_id
                            if delivery_id is not None
                            else WebhookEventRecord.event_id == event_id,
                        )
                    )
                )
                if existing_event and existing_event.state != "failed":
                    return "duplicate_delivery"
                if existing_event:
                    if not claim_message or not message_id:
                        return "duplicate_delivery"
                    if session.get(WebhookMessageClaim, message_id):
                        return "duplicate_message"
                    session.add(WebhookMessageClaim(
                        message_id=message_id,
                        event_id=event_id,
                    ))
                    existing_event.state = state
                    existing_event.analysis_id = None
                    return state
                if claim_message and message_id:
                    if session.get(WebhookMessageClaim, message_id):
                        duplicate_state = "duplicate_message"
                        analysis_state = duplicate_state
                    else:
                        session.add(WebhookMessageClaim(
                            message_id=message_id,
                            event_id=event_id,
                        ))
                        analysis_state = state
                else:
                    analysis_state = state
                session.add(WebhookEventRecord(
                    event_id=event_id,
                    delivery_id=delivery_id,
                    message_id=message_id,
                    event_type=event_type,
                    state=analysis_state,
                    sender=sender,
                    recipient=recipient,
                    subject=subject,
                ))
                return analysis_state
        except IntegrityError:
            return "duplicate_delivery"
        except SQLAlchemyError as exc:
            raise PersistenceError("Webhook event persistence failed") from exc

    def update_webhook_event(
        self, event_id: str, state: str, analysis_id: str | None = None
    ) -> None:
        try:
            with self._session_factory.begin() as session:
                event = session.get(WebhookEventRecord, event_id)
                if event is None:
                    return
                event.state = state
                event.analysis_id = analysis_id
                if state == "failed":
                    session.execute(
                        delete(WebhookMessageClaim).where(
                            WebhookMessageClaim.event_id == event_id
                        )
                    )
        except SQLAlchemyError as exc:
            raise PersistenceError("Webhook event update failed") from exc


@lru_cache(maxsize=4)
def get_database() -> Database:
    return Database(get_settings().database_url)