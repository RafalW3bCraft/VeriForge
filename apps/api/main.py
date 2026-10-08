import logging
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from config import get_settings
from database import PersistenceError, get_database
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
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

_rate_limit_cache: dict[str, deque[float]] = defaultdict(deque)


def _error_code_for(status_code: int) -> str:
    return {
        400: "INVALID_REQUEST",
        401: "UNAUTHORIZED",
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

@app.post("/api/v1/analyze", response_model=AnalysisResponse)
async def analyze_endpoint(req: AnalysisRequest):
    try:
        result = await analyze(req.content, req.input_type, req.context)
        get_database().save_analysis(result)
        return result
    except PersistenceError as exc:
        raise HTTPException(
            status_code=503, detail="Analysis result could not be persisted"
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/analyses", response_model=AnalysisListResponse)
def list_analyses(limit: int = Query(default=20, ge=1, le=100)):
    try:
        return {"items": get_database().list_analyses(limit)}
    except PersistenceError as exc:
        raise HTTPException(status_code=503, detail="Analysis history is unavailable") from exc


@app.get("/api/v1/analyses/{analysis_id}", response_model=AnalysisResponse)
def get_analysis(analysis_id: str):
    try:
        result = get_database().get_analysis(analysis_id)
    except PersistenceError as exc:
        raise HTTPException(status_code=503, detail="Analysis history is unavailable") from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return result


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
        )
        return WebhookAcknowledgement(
            status="accepted", event_id=event.event_id, message_id=message_id
        )
    return WebhookAcknowledgement(
        status="skipped", event_id=event.event_id, message_id=message_id
    )
