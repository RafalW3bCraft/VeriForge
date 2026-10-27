import logging
import hashlib
import hmac
import secrets
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse

from config import get_settings
from database import AnalysisRecord, PersistenceError, get_database
from engine import analyze
from integrations.agentboxd import (
    MAIL_EVENTS,
    AgentboxdPayloadError,
    get_message_metadata,
    normalize_message_event,
    parse_webhook_event,
    process_normalized_message,
    verify_webhook_signature,
)
from models import (
    AnalysisListResponse,
    AnalysisRequest,
    AnalysisResponse,
    WebhookAcknowledgement,
    CreateUserRequest,
    InvestigationGrantRequest,
    InvestigationReviewRequest,
    LoginRequest,
)

logger = logging.getLogger("veriforge.api")
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_settings().validate_runtime()
    yield


app = FastAPI(title="VeriForge API", version="0.1.0", lifespan=lifespan)

allow_origins = list(settings.cors_origins or ["http://localhost:5173", "http://127.0.0.1:5173"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

def mount_frontend_assets(application: FastAPI, dist_dir: Path) -> bool:
    """Mount a Vite bundle only when its generated assets actually exist."""
    assets_dir = dist_dir / "assets"
    # A clean checkout intentionally does not contain Vite output. `StaticFiles`
    # validates its directory eagerly, so checking only `dist` makes importing
    # the backend fail when a stale index exists without generated assets.
    if not assets_dir.is_dir():
        return False
    application.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
    return True


frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
mount_frontend_assets(app, frontend_dist)

_rate_limit_cache: dict[str, deque[float]] = defaultdict(deque)
_login_limit_cache: dict[str, deque[float]] = defaultdict(deque)
SESSION_COOKIE = "veriforge_session"
CSRF_HEADER = "X-CSRF-Token"


@dataclass(frozen=True)
class Principal:
    user_id: str | None
    tenant_id: str
    role: str
    csrf_hash: str | None = None

    @property
    def is_legacy(self) -> bool:
        return self.user_id is None


def get_current_principal(request: Request) -> Principal:
    database = get_database()
    raw_token = request.cookies.get(SESSION_COOKIE)
    if not raw_token:
        if get_settings().bootstrap_admin_username:
            raise HTTPException(status_code=401, detail="Authentication required")
        # Backwards-compatible single-user mode. It is disabled automatically
        # as soon as the explicit bootstrap administrator is configured.
        return Principal(user_id=None, tenant_id="legacy", role="admin")
    result = database.get_session_user(raw_token)
    if result is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    user, csrf_hash = result
    return Principal(user_id=user.user_id, tenant_id=user.tenant_id, role=user.role, csrf_hash=csrf_hash)


def require_authenticated(principal: Principal = Depends(get_current_principal)) -> Principal:
    if principal.is_legacy:
        raise HTTPException(status_code=401, detail="Authentication required")
    return principal


def require_admin(principal: Principal = Depends(require_authenticated)) -> Principal:
    if principal.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")
    return principal


def require_write_principal(request: Request, principal: Principal = Depends(get_current_principal)) -> Principal:
    if principal.role == "viewer":
        raise HTTPException(status_code=403, detail="This account is read-only")
    if not principal.is_legacy:
        supplied = request.headers.get(CSRF_HEADER)
        if not supplied or not principal.csrf_hash or not hmac.compare_digest(
            hashlib.sha256(supplied.encode("utf-8")).hexdigest(), principal.csrf_hash
        ):
            raise HTTPException(status_code=403, detail="CSRF validation failed")
    return principal


def _error_code_for(status_code: int) -> str:
    return {
        400: "INVALID_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        413: "REQUEST_TOO_LARGE",
        429: "RATE_LIMITED",
        500: "INTERNAL_ERROR",
        503: "SERVICE_UNAVAILABLE",
    }.get(status_code, "HTTP_ERROR")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    code = exc.status_code
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return JSONResponse(
        status_code=code,
        content={"error": {"code": _error_code_for(code), "message": message}},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled API exception", extra={"path": request.url.path})
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "The request could not be processed."}},
    )


@app.middleware("http")
async def security_and_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    start = time.perf_counter()

    if request.method in {"POST", "PUT", "PATCH"}:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > get_settings().max_request_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={"error": {"code": "REQUEST_TOO_LARGE", "message": "Request body exceeds the configured limit."}},
                    )
            except ValueError:
                pass

    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    bucket = _rate_limit_cache[client_ip]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= get_settings().rate_limit_per_minute:
        logger.warning(
            "Rate limit exceeded",
            extra={"request_id": request_id, "path": request.url.path, "client_ip": client_ip},
        )
        return JSONResponse(
            status_code=429,
            content={"error": {"code": "RATE_LIMITED", "message": "Too many requests. Try again shortly."}},
        )
    bucket.append(now)

    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Request-ID"] = request_id
    response.headers["Vary"] = "Origin"
    if request.url.path.startswith("/api"):
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"

    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.info(
        "api_request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "client_ip": client_ip,
        },
    )
    return response


@app.get("/", include_in_schema=False)
async def root_page():
    if frontend_dist.exists() and (frontend_dist / "index.html").exists():
        return FileResponse(frontend_dist / "index.html")
    return {"status": "ok", "service": "veriforge-api"}


@app.get("/history", include_in_schema=False)
@app.get("/new", include_in_schema=False)
@app.get("/help", include_in_schema=False)
@app.get("/analysis/{analysis_id:path}", include_in_schema=False)
async def spa_fallback(analysis_id: str | None = None):
    if frontend_dist.exists() and (frontend_dist / "index.html").exists():
        return FileResponse(frontend_dist / "index.html")
    return {"status": "ok", "service": "veriforge-api"}


@app.get("/health")
def health():
    return {"status": "ok", "service": "veriforge-api"}


@app.get("/ready")
def ready():
    try:
        get_database()
    except Exception as exc:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ready", "service": "veriforge-api", "demo_mode": get_settings().demo_mode}


@app.post("/api/v1/auth/login")
def login(credentials: LoginRequest, request: Request, response: Response):
    """Create an opaque, server-side session; there is intentionally no signup."""
    database = get_database()
    if not database.accounts_enabled():
        raise HTTPException(status_code=503, detail="Local accounts are not configured")
    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    attempts = _login_limit_cache[client_ip]
    while attempts and now - attempts[0] > 300:
        attempts.popleft()
    if len(attempts) >= 5:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later")
    user = database.authenticate_user(credentials.username, credentials.password)
    if user is None:
        attempts.append(now)
        raise HTTPException(status_code=401, detail="Invalid username or password")
    attempts.clear()
    csrf_token = secrets.token_urlsafe(32)
    raw_session = database.create_session(user.user_id, csrf_token)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=raw_session,
        httponly=True,
        secure=get_settings().session_cookie_secure,
        samesite="strict",
        max_age=get_settings().session_hours * 3600,
        path="/",
    )
    return {
        "user": {"id": user.user_id, "username": user.username, "role": user.role},
        # The token is returned once over the same-origin TLS response and is
        # never persisted client-side by the API.
        "csrf_token": csrf_token,
    }


@app.get("/api/v1/auth/mode")
def auth_mode():
    """Allow the same frontend bundle to distinguish local legacy/demo mode."""
    return {"accounts_enabled": get_database().accounts_enabled()}


@app.post("/api/v1/auth/logout", status_code=204)
def logout(request: Request, response: Response, principal: Principal = Depends(require_write_principal)):
    raw_token = request.cookies.get(SESSION_COOKIE)
    if raw_token:
        get_database().delete_session(raw_token)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@app.get("/api/v1/auth/me")
def current_account(principal: Principal = Depends(require_authenticated)):
    return {"id": principal.user_id, "tenant_id": principal.tenant_id, "role": principal.role}

# Optional API-key authorization for analysis history. When VERIFORGE_API_KEY
# is set, history endpoints require the X-API-Key header. When unset the
# deployment is single-user local and history stays open (documented).
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_history_access(
    principal: Principal = Depends(get_current_principal),
    api_key: str | None = Depends(_api_key_header),
) -> Principal:
    configured = get_settings().api_key
    # API keys remain a migration aid for the legacy single-user mode only;
    # account deployments authorize from the server-side session.
    if not get_settings().bootstrap_admin_username and configured is not None and not hmac.compare_digest(api_key or "", configured):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return principal


@app.post("/api/v1/analyze", response_model=AnalysisResponse)
async def analyze_endpoint(
    req: AnalysisRequest,
    principal: Principal = Depends(require_write_principal),
):
    try:
        # Context is analyst-provided evidence context, never an authorization
        # channel. Tenant and investigation scope come exclusively from the
        # authenticated server-side principal.
        safe_context = dict(req.context or {})
        safe_context.pop("tenant_id", None)
        safe_context.pop("investigation_id", None)
        if not principal.is_legacy:
            safe_context["tenant_id"] = principal.tenant_id
        result = await analyze(req.content, req.input_type, safe_context)
        # Keep the original call signature in single-user mode for downstream
        # integrations, while accounts always attach server-derived ownership.
        if principal.is_legacy:
            get_database().save_analysis(result)
        else:
            get_database().save_analysis(
                result, tenant_id=principal.tenant_id, owner_id=principal.user_id
            )
        return result
    except PersistenceError as exc:
        raise HTTPException(
            status_code=503, detail="Analysis result could not be persisted"
        ) from exc
    except Exception as exc:
        # Never leak internal exception text to clients (baseline defect)
        logger.exception("Analysis failed", extra={"input_type": req.input_type})
        raise HTTPException(status_code=500, detail="Analysis could not be completed") from exc


@app.get("/api/v1/analyses", response_model=AnalysisListResponse)
def list_analyses(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(require_history_access),
):
    try:
        if principal.is_legacy:
            return {"items": get_database().list_analyses(limit, offset=offset)}
        return {"items": get_database().list_analyses(
            limit, tenant_id=principal.tenant_id, user_id=principal.user_id,
            role=principal.role, offset=offset,
        )}
    except PersistenceError as exc:
        raise HTTPException(status_code=503, detail="Analysis history is unavailable") from exc


@app.get("/api/v1/integrations/status")
def integrations_status():
    """Truthful sponsor-integration health — never mocked."""
    from integrations.zetaris.client import get_zetaris_client
    from hmem.engine import get_hmem_engine

    zetaris = get_zetaris_client()
    hmem_health = get_hmem_engine().health()
    return {
        "zetaris": zetaris.health(),
        "hmem": hmem_health,
    }


@app.get("/api/v1/analyses/{analysis_id}", response_model=AnalysisResponse)
def get_analysis(analysis_id: str, principal: Principal = Depends(require_history_access)):
    try:
        if principal.is_legacy:
            result = get_database().get_analysis(analysis_id)
        else:
            result = get_database().get_analysis(
                analysis_id, tenant_id=principal.tenant_id,
                user_id=principal.user_id, role=principal.role,
            )
    except PersistenceError as exc:
        raise HTTPException(status_code=503, detail="Analysis history is unavailable") from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return result


def _authorized_analysis(analysis_id: str, principal: Principal):
    if principal.is_legacy:
        result = get_database().get_analysis(analysis_id)
    else:
        result = get_database().get_analysis(
            analysis_id, tenant_id=principal.tenant_id, user_id=principal.user_id,
            role=principal.role,
        )
    if result is None:
        # Avoid turning a cross-tenant identifier into an existence oracle.
        raise HTTPException(status_code=404, detail="Analysis not found")
    return result


@app.get("/api/v1/analyses/{analysis_id}/export")
def export_analysis(
    analysis_id: str,
    format: str = Query(default="json", pattern="^(json|html)$"),
    principal: Principal = Depends(require_history_access),
):
    result = _authorized_analysis(analysis_id, principal)
    if format == "json":
        return result.model_dump(mode="json")
    from html import escape
    payload = result.model_dump(mode="json")
    title = escape(f"VeriForge investigation {result.analysis_id}")
    body = escape(str(payload))
    return HTMLResponse(
        f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title></head>"
        f"<body><main><h1>{title}</h1><p>Verdict: {escape(result.verdict)}</p>"
        f"<pre>{body}</pre></main></body></html>",
        headers={"Content-Disposition": f'attachment; filename="veriforge-{analysis_id}.html"'},
    )


@app.post("/api/v1/analyses/{analysis_id}/grants", status_code=204)
def grant_analysis(
    analysis_id: str,
    grant: InvestigationGrantRequest,
    principal: Principal = Depends(require_write_principal),
):
    _authorized_analysis(analysis_id, principal)
    if principal.is_legacy:
        raise HTTPException(status_code=503, detail="Local accounts are not configured")
    # Only investigation owners and administrators can share an investigation.
    if principal.role != "admin":
        with get_database()._session_factory() as session:
            row = session.get(AnalysisRecord, analysis_id)
            if row is None or row.owner_id != principal.user_id:
                raise HTTPException(status_code=403, detail="Only the investigation owner can grant access")
    try:
        get_database().grant_analysis_access(
            analysis_id, grant.user_id, tenant_id=principal.tenant_id, actor_id=principal.user_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/v1/analyses/{analysis_id}/review", status_code=204)
def review_analysis(
    analysis_id: str,
    review: InvestigationReviewRequest,
    principal: Principal = Depends(require_write_principal),
):
    _authorized_analysis(analysis_id, principal)
    if principal.is_legacy:
        raise HTTPException(status_code=503, detail="Local accounts are not configured")
    if not get_database().review_analysis(
        analysis_id, tenant_id=principal.tenant_id, actor_id=principal.user_id,
        review_status=review.status, notes=review.notes,
    ):
        raise HTTPException(status_code=404, detail="Analysis not found")


@app.post("/api/v1/analyses/{analysis_id}/archive", status_code=204)
def archive_analysis(
    analysis_id: str,
    principal: Principal = Depends(require_write_principal),
):
    _authorized_analysis(analysis_id, principal)
    if principal.is_legacy:
        raise HTTPException(status_code=503, detail="Local accounts are not configured")
    if principal.role != "admin":
        with get_database()._session_factory() as session:
            row = session.get(AnalysisRecord, analysis_id)
            if row is None or row.owner_id != principal.user_id:
                raise HTTPException(status_code=403, detail="Only the investigation owner can archive it")
    if not get_database().archive_analysis(
        analysis_id, tenant_id=principal.tenant_id, actor_id=principal.user_id
    ):
        raise HTTPException(status_code=404, detail="Analysis not found")


@app.get("/api/v1/admin/users")
def admin_users(principal: Principal = Depends(require_admin)):
    return {"items": [
        {"id": user.user_id, "username": user.username, "role": user.role, "active": user.active}
        for user in get_database().list_users(principal.tenant_id)
    ]}


@app.post("/api/v1/admin/users", status_code=201)
def create_user(user: CreateUserRequest, principal: Principal = Depends(require_write_principal)):
    if principal.is_legacy or principal.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")
    try:
        created = get_database().create_user(
            username=user.username, password=user.password, role=user.role,
            tenant_id=principal.tenant_id, actor_id=principal.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": created.user_id, "username": created.username, "role": created.role}


@app.get("/api/v1/admin/audit")
def admin_audit(
    limit: int = Query(default=100, ge=1, le=500),
    principal: Principal = Depends(require_admin),
):
    return {"items": [
        {"id": item.event_id, "actor_id": item.actor_id, "action": item.action,
         "resource_type": item.resource_type, "resource_id": item.resource_id,
         "detail": item.detail, "created_at": item.created_at}
        for item in get_database().list_audit_events(principal.tenant_id, limit)
    ]}


@app.post(
    "/api/v1/webhooks/agentboxd",
    response_model=WebhookAcknowledgement,
)
async def agentboxd_webhook(
    request: Request, background_tasks: BackgroundTasks
) -> WebhookAcknowledgement:
    settings = get_settings()
    secret = settings.agentboxd_webhook_secret
    if not secret:
        raise HTTPException(status_code=503, detail="Webhook is not configured")

    max_bytes = settings.max_input_chars * 4 + 65536
    raw_body = bytearray()
    async for chunk in request.stream():
        raw_body.extend(chunk)
        if len(raw_body) > max_bytes:
            raise HTTPException(status_code=413, detail="Webhook payload too large")
    raw_bytes = bytes(raw_body)

    signature = request.headers.get("X-Mailroom-Signature")
    timestamp = request.headers.get("X-Mailroom-Timestamp")
    if not verify_webhook_signature(signature, timestamp, raw_bytes, secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        event = parse_webhook_event(raw_bytes)
    except AgentboxdPayloadError as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook payload") from exc

    delivery_id = request.headers.get("X-Mailroom-Delivery")
    message = event.data.get("message")
    message_id = (
        message.get("id") if isinstance(message, dict) else event.data.get("message_id")
    )
    message_id = message_id if isinstance(message_id, str) else None
    sender = None
    recipient = None
    subject = None
    if isinstance(message, dict):
        sender = message.get("from") if isinstance(message.get("from"), str) else None
        raw_recipients = message.get("to")
        if isinstance(raw_recipients, list) and raw_recipients:
            recipient = raw_recipients[0] if isinstance(raw_recipients[0], str) else None
        elif isinstance(raw_recipients, str):
            recipient = raw_recipients
        subject = message.get("subject") if isinstance(message.get("subject"), str) else None

    normalized = None
    metadata = get_message_metadata(event)
    if event.event_type not in MAIL_EVENTS:
        state = "ignored_event"
    elif isinstance(message, dict) and message.get("auto_reply") is True:
        state = "auto_reply"
    elif isinstance(message, dict) and message.get("withheld"):
        state = "withheld"
    else:
        try:
            normalized = normalize_message_event(event)
            state = "accepted"
            message_id = normalized.message_id
            sender = normalized.sender
            recipient = normalized.recipient
            subject = normalized.subject
        except AgentboxdPayloadError as exc:
            if "body is missing" in str(exc) or "Full message payload" in str(exc):
                state = "body_unavailable"
            else:
                raise HTTPException(status_code=422, detail="Invalid email event") from exc

    try:
        accepted_state = get_database().accept_webhook_event(
            event_id=event.event_id,
            delivery_id=delivery_id,
            message_id=message_id,
            event_type=event.event_type,
            state=state,
            sender=sender,
            recipient=recipient,
            subject=subject,
            claim_message=normalized is not None,
        )
    except PersistenceError as exc:
        raise HTTPException(status_code=503, detail="Webhook could not be accepted") from exc

    if accepted_state in {"duplicate_delivery", "duplicate_message"}:
        return WebhookAcknowledgement(
            status="duplicate", event_id=event.event_id, message_id=message_id
        )
    if normalized is not None:
        background_tasks.add_task(
            process_normalized_message,
            event.event_id,
            normalized,
            metadata,
            tenant_id=settings.agentboxd_tenant_id,
        )
        return WebhookAcknowledgement(
            status="accepted", event_id=event.event_id, message_id=message_id
        )
    return WebhookAcknowledgement(
        status="skipped", event_id=event.event_id, message_id=message_id
    )
