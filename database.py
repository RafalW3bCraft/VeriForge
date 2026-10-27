import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    Boolean,
    Float,
    ForeignKey,
    JSON,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    delete,
    inspect,
    select,
    text,
    update,
    or_,
)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from config import get_settings
from models import AnalysisResponse, AnalysisSummary


class Base(DeclarativeBase):
    pass


class TenantRecord(Base):
    __tablename__ = "tenants"

    tenant_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UserRecord(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "username", name="uq_user_tenant_username"),)

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id", ondelete="CASCADE"), index=True)
    username: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(16), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SessionRecord(Base):
    """Only digests are persisted; a database disclosure cannot replay a cookie."""

    __tablename__ = "sessions"

    session_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class InvestigationGrantRecord(Base):
    __tablename__ = "investigation_grants"
    __table_args__ = (UniqueConstraint("analysis_id", "user_id", name="uq_analysis_user_grant"),)

    grant_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.analysis_id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), index=True)
    granted_by: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditEventRecord(Base):
    __tablename__ = "audit_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(80))
    resource_type: Mapped[str] = mapped_column(String(40))
    resource_id: Mapped[str | None] = mapped_column(String(100))
    # Deliberately redacted metadata only; never request bodies or credentials.
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


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
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    owner_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    review_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)


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


LEGACY_TENANT_ID = "legacy"
VALID_ROLES = frozenset({"admin", "analyst", "viewer"})
# Valid Argon2id hash for a non-secret dummy value. It makes unknown-user and
# inactive-user attempts take the same expensive verification path as a bad
# password without persisting a decoy account.
_DUMMY_PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$nYMdfV/d9J3u0oYLsa3fmA$TjUntsBstrmtHdPruHqe8+X1HfBJELH/e5MuwUp+yK4"


def _secret_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _password_hash(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Passwords must be at least 12 characters")
    try:
        from argon2 import PasswordHasher
    except ImportError as exc:  # pragma: no cover - dependency is required in production
        raise PersistenceError("Argon2 password support is unavailable") from exc
    return PasswordHasher().hash(password)


def _verify_password(password_hash: str, password: str) -> bool:
    try:
        from argon2 import PasswordHasher
        from argon2.exceptions import VerifyMismatchError
    except ImportError as exc:  # pragma: no cover - dependency is required in production
        raise PersistenceError("Argon2 password support is unavailable") from exc
    try:
        return PasswordHasher().verify(password_hash, password)
    except VerifyMismatchError:
        return False


class Database:
    def __init__(self, url: str):
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.engine = create_engine(url, connect_args=connect_args)
        self._session_factory = sessionmaker(self.engine, expire_on_commit=False)
        try:
            Base.metadata.create_all(self.engine)
            self._migrate_legacy_schema()
            self._ensure_security_records()
        except SQLAlchemyError as exc:
            raise PersistenceError("Database initialization failed") from exc
        self.prune_expired()

    def _migrate_legacy_schema(self) -> None:
        """Small, idempotent SQLite-safe bridge for databases made before accounts.

        New deployments receive these columns through metadata creation.  Existing
        prototype databases cannot be discarded during an upgrade, so keep this
        intentionally additive migration until Alembic is introduced for releases.
        """
        columns = {column["name"] for column in inspect(self.engine).get_columns("analyses")}
        additions = {
            "tenant_id": "VARCHAR(36)",
            "owner_id": "VARCHAR(36)",
            "status": "VARCHAR(20) DEFAULT 'active'",
            "review_status": "VARCHAR(20)",
            "review_notes": "TEXT",
        }
        with self.engine.begin() as connection:
            for name, column_type in additions.items():
                if name not in columns:
                    connection.execute(text(f"ALTER TABLE analyses ADD COLUMN {name} {column_type}"))

    def _ensure_security_records(self) -> None:
        settings = get_settings()
        if bool(settings.bootstrap_admin_username) != bool(settings.bootstrap_admin_password):
            raise PersistenceError(
                "Both VERIFORGE_BOOTSTRAP_ADMIN_USERNAME and VERIFORGE_BOOTSTRAP_ADMIN_PASSWORD are required"
            )
        now = datetime.now(timezone.utc)
        with self._session_factory.begin() as session:
            legacy = session.get(TenantRecord, LEGACY_TENANT_ID)
            if legacy is None:
                session.add(TenantRecord(
                    tenant_id=LEGACY_TENANT_ID,
                    name="Legacy VeriForge",
                    created_at=now,
                ))
            # All historical records remain accessible only within the legacy
            # tenant after accounts are enabled.
            session.execute(
                update(AnalysisRecord)
                .where(AnalysisRecord.tenant_id.is_(None))
                .values(tenant_id=LEGACY_TENANT_ID, status="active")
            )
            if not settings.bootstrap_admin_username:
                return
            username = settings.bootstrap_admin_username.strip()
            existing = session.scalar(
                select(UserRecord).where(
                    UserRecord.tenant_id == LEGACY_TENANT_ID,
                    UserRecord.username == username,
                )
            )
            if existing is None:
                existing = UserRecord(
                    user_id=str(uuid4()),
                    tenant_id=LEGACY_TENANT_ID,
                    username=username,
                    password_hash=_password_hash(settings.bootstrap_admin_password or ""),
                    role="admin",
                    active=True,
                    created_at=now,
                )
                session.add(existing)
            session.execute(
                update(AnalysisRecord)
                .where(
                    AnalysisRecord.tenant_id == LEGACY_TENANT_ID,
                    AnalysisRecord.owner_id.is_(None),
                )
                .values(owner_id=existing.user_id)
            )

    def accounts_enabled(self) -> bool:
        return get_settings().bootstrap_admin_username is not None

    def authenticate_user(self, username: str, password: str) -> UserRecord | None:
        """Authenticate without exposing whether a username exists."""
        try:
            with self._session_factory() as session:
                user = session.scalar(
                    select(UserRecord).where(
                        UserRecord.tenant_id == LEGACY_TENANT_ID,
                        UserRecord.username == username.strip(),
                    )
                )
                if user is None or not user.active:
                    _verify_password(_DUMMY_PASSWORD_HASH, password)
                    return None
                if not _verify_password(user.password_hash, password):
                    return None
                return user
        except SQLAlchemyError as exc:
            raise PersistenceError("Authentication lookup failed") from exc

    def create_session(self, user_id: str, csrf_token: str) -> str:
        raw_token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=get_settings().session_hours)
        try:
            with self._session_factory.begin() as session:
                session.add(SessionRecord(
                    session_hash=_secret_digest(raw_token),
                    user_id=user_id,
                    csrf_hash=_secret_digest(csrf_token),
                    created_at=now,
                    expires_at=expires,
                ))
            return raw_token
        except SQLAlchemyError as exc:
            raise PersistenceError("Session could not be created") from exc

    def get_session_user(self, raw_token: str) -> tuple[UserRecord, str] | None:
        try:
            with self._session_factory() as session:
                record = session.get(SessionRecord, _secret_digest(raw_token))
                expires_at = record.expires_at if record is not None else None
                if expires_at is not None and expires_at.tzinfo is None:
                    # SQLite returns naive values even for timezone=True.
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if record is None or expires_at is None or expires_at <= datetime.now(timezone.utc):
                    return None
                user = session.get(UserRecord, record.user_id)
                if user is None or not user.active:
                    return None
                return user, record.csrf_hash
        except SQLAlchemyError as exc:
            raise PersistenceError("Session lookup failed") from exc

    def delete_session(self, raw_token: str) -> None:
        try:
            with self._session_factory.begin() as session:
                session.execute(delete(SessionRecord).where(SessionRecord.session_hash == _secret_digest(raw_token)))
        except SQLAlchemyError as exc:
            raise PersistenceError("Session could not be removed") from exc

    def create_user(self, *, username: str, password: str, role: str, tenant_id: str, actor_id: str) -> UserRecord:
        if role not in VALID_ROLES:
            raise ValueError("Invalid role")
        normalized = username.strip()
        if not normalized or len(normalized) > 80:
            raise ValueError("Invalid username")
        try:
            with self._session_factory.begin() as session:
                user = UserRecord(
                    user_id=str(uuid4()), tenant_id=tenant_id, username=normalized,
                    password_hash=_password_hash(password), role=role, active=True,
                    created_at=datetime.now(timezone.utc),
                )
                session.add(user)
                self._audit(session, tenant_id, actor_id, "user.created", "user", user.user_id, {"role": role})
                return user
        except IntegrityError as exc:
            raise ValueError("Username already exists") from exc
        except SQLAlchemyError as exc:
            raise PersistenceError("User could not be created") from exc

    def list_users(self, tenant_id: str) -> list[UserRecord]:
        try:
            with self._session_factory() as session:
                return session.scalars(select(UserRecord).where(UserRecord.tenant_id == tenant_id).order_by(UserRecord.username)).all()
        except SQLAlchemyError as exc:
            raise PersistenceError("User lookup failed") from exc

    @staticmethod
    def _audit(session: Any, tenant_id: str, actor_id: str | None, action: str, resource_type: str, resource_id: str | None, detail: dict[str, Any] | None = None) -> None:
        session.add(AuditEventRecord(
            event_id=str(uuid4()), tenant_id=tenant_id, actor_id=actor_id,
            action=action, resource_type=resource_type, resource_id=resource_id,
            detail=detail or {}, created_at=datetime.now(timezone.utc),
        ))

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
                session.execute(
                    delete(SessionRecord).where(
                        SessionRecord.expires_at < datetime.now(timezone.utc)
                    )
                )
                return len(expired_ids)
        except SQLAlchemyError as exc:
            raise PersistenceError("Retention cleanup failed") from exc

    def save_analysis(
        self,
        response: AnalysisResponse,
        *,
        tenant_id: str = LEGACY_TENANT_ID,
        owner_id: str | None = None,
    ) -> None:
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
                    tenant_id=tenant_id,
                    owner_id=owner_id,
                    status="active",
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

    def list_analyses(
        self,
        limit: int = 20,
        *,
        tenant_id: str | None = None,
        user_id: str | None = None,
        role: str | None = None,
        include_archived: bool = False,
        offset: int = 0,
    ) -> list[AnalysisSummary]:
        try:
            with self._session_factory() as session:
                statement = select(AnalysisRecord)
                if tenant_id is not None:
                    statement = statement.where(AnalysisRecord.tenant_id == tenant_id)
                if not include_archived:
                    statement = statement.where(AnalysisRecord.status != "archived")
                # Administrators see their tenant.  Other authenticated users
                # see records they own or which have an explicit grant.
                if user_id is not None and role != "admin":
                    statement = statement.where(
                        or_(
                            AnalysisRecord.owner_id == user_id,
                            AnalysisRecord.analysis_id.in_(
                                select(InvestigationGrantRecord.analysis_id).where(
                                    InvestigationGrantRecord.user_id == user_id
                                )
                            ),
                        )
                    )
                rows = session.scalars(statement.order_by(AnalysisRecord.created_at.desc()).offset(offset).limit(limit)).all()
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

    def get_analysis(
        self,
        analysis_id: str,
        *,
        tenant_id: str | None = None,
        user_id: str | None = None,
        role: str | None = None,
    ) -> AnalysisResponse | None:
        try:
            with self._session_factory() as session:
                row = session.get(AnalysisRecord, analysis_id)
                if row is None:
                    return None
                if tenant_id is not None and row.tenant_id != tenant_id:
                    return None
                if user_id is not None and role != "admin" and row.owner_id != user_id:
                    granted = session.scalar(
                        select(InvestigationGrantRecord.grant_id).where(
                            InvestigationGrantRecord.analysis_id == analysis_id,
                            InvestigationGrantRecord.user_id == user_id,
                        )
                    )
                    if granted is None:
                        return None
                return AnalysisResponse.model_validate(row.result_json)
        except SQLAlchemyError as exc:
            raise PersistenceError("Analysis lookup failed") from exc

    def grant_analysis_access(self, analysis_id: str, user_id: str, *, tenant_id: str, actor_id: str) -> None:
        try:
            with self._session_factory.begin() as session:
                analysis = session.get(AnalysisRecord, analysis_id)
                user = session.get(UserRecord, user_id)
                if analysis is None or user is None or analysis.tenant_id != tenant_id or user.tenant_id != tenant_id:
                    raise ValueError("Investigation or user not found")
                session.add(InvestigationGrantRecord(
                    grant_id=str(uuid4()), analysis_id=analysis_id, user_id=user_id,
                    granted_by=actor_id, created_at=datetime.now(timezone.utc),
                ))
                self._audit(session, tenant_id, actor_id, "investigation.granted", "analysis", analysis_id, {"user_id": user_id})
        except IntegrityError:
            return
        except SQLAlchemyError as exc:
            raise PersistenceError("Access grant could not be saved") from exc

    def review_analysis(self, analysis_id: str, *, tenant_id: str, actor_id: str, review_status: str, notes: str | None) -> bool:
        if review_status not in {"open", "reviewed", "resolved"}:
            raise ValueError("Invalid review status")
        try:
            with self._session_factory.begin() as session:
                row = session.get(AnalysisRecord, analysis_id)
                if row is None or row.tenant_id != tenant_id:
                    return False
                row.review_status = review_status
                row.review_notes = (notes or "").strip()[:2000] or None
                self._audit(session, tenant_id, actor_id, "investigation.reviewed", "analysis", analysis_id, {"status": review_status})
                return True
        except SQLAlchemyError as exc:
            raise PersistenceError("Review could not be saved") from exc

    def archive_analysis(self, analysis_id: str, *, tenant_id: str, actor_id: str) -> bool:
        try:
            with self._session_factory.begin() as session:
                row = session.get(AnalysisRecord, analysis_id)
                if row is None or row.tenant_id != tenant_id:
                    return False
                row.status = "archived"
                self._audit(session, tenant_id, actor_id, "investigation.archived", "analysis", analysis_id)
                return True
        except SQLAlchemyError as exc:
            raise PersistenceError("Investigation could not be archived") from exc

    def list_audit_events(self, tenant_id: str, limit: int = 100) -> list[AuditEventRecord]:
        try:
            with self._session_factory() as session:
                return session.scalars(select(AuditEventRecord).where(AuditEventRecord.tenant_id == tenant_id).order_by(AuditEventRecord.created_at.desc()).limit(limit)).all()
        except SQLAlchemyError as exc:
            raise PersistenceError("Audit lookup failed") from exc

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
