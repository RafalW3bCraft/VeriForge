import os
import math
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _read_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def _read_positive_int(name: str, default: int) -> int:
    value = os.getenv(name)
    try:
        parsed = default if value is None else int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if parsed < 1:
        raise ValueError(f"{name} must be a positive integer")
    return parsed


def _read_nonnegative_int(name: str, default: int) -> int:
    value = os.getenv(name)
    try:
        parsed = default if value is None else int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a nonnegative integer") from exc
    if parsed < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return parsed


def _read_positive_float(name: str, default: float) -> float:
    value = os.getenv(name)
    try:
        parsed = default if value is None else float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive number") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be a positive number")
    return parsed


def _read_nonnegative_float(name: str, default: float) -> float:
    value = os.getenv(name)
    try:
        parsed = default if value is None else float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a nonnegative number") from exc
    if parsed < 0:
        raise ValueError(f"{name} must be a nonnegative number")
    return parsed


@dataclass(frozen=True)
class Settings:
    demo_mode: bool
    featherless_api_key: str | None
    featherless_base_url: str
    featherless_model: str
    agentboxd_api_key: str | None
    agentboxd_webhook_secret: str | None
    agentboxd_base_url: str
    database_url: str
    cors_origins: tuple[str, ...]
    rate_limit_per_minute: int
    retention_days: int
    log_level: str
    max_input_chars: int
    max_request_bytes: int
    featherless_timeout_seconds: float
    featherless_max_retries: int
    risk_weights: tuple[float, float, float, float]

    def validate_runtime(self) -> None:
        if not self.demo_mode and not self.featherless_api_key:
            raise RuntimeError("FEATHERLESS_API_KEY is required when DEMO_MODE is false")


def get_settings() -> Settings:
    cors_origins = tuple(
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if origin.strip()
    )
    risk_weights = (
        _read_nonnegative_float("RISK_WEIGHT_IDENTITY", 0.25),
        _read_nonnegative_float("RISK_WEIGHT_INFRASTRUCTURE", 0.30),
        _read_nonnegative_float("RISK_WEIGHT_SOCIAL", 0.20),
        _read_nonnegative_float("RISK_WEIGHT_VERIFICATION", 0.25),
    )
    if not math.isclose(sum(risk_weights), 1.0, rel_tol=0.0, abs_tol=1e-6):
        raise ValueError("Risk weights must sum to 1")
    return Settings(
        demo_mode=_read_bool("DEMO_MODE", False),
        featherless_api_key=os.getenv("FEATHERLESS_API_KEY") or None,
        featherless_base_url=os.getenv(
            "FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1"
        ),
        featherless_model=os.getenv("FEATHERLESS_MODEL", "Qwen/Qwen3.5-27B"),
        agentboxd_api_key=os.getenv("AGENTBOXD_API_KEY") or None,
        agentboxd_webhook_secret=os.getenv("AGENTBOXD_WEBHOOK_SECRET") or None,
        agentboxd_base_url=os.getenv("AGENTBOXD_BASE_URL", "https://api.agentboxd.com"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./veriforge.db"),
        cors_origins=cors_origins,
        rate_limit_per_minute=_read_positive_int("RATE_LIMIT", 60),
        retention_days=_read_positive_int("RETENTION_DAYS", 30),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        max_input_chars=_read_positive_int("MAX_INPUT_CHARS", 30000),
        max_request_bytes=_read_positive_int("MAX_REQUEST_BYTES", 131072),
        featherless_timeout_seconds=_read_positive_float(
            "FEATHERLESS_TIMEOUT_SECONDS", 30.0
        ),
        featherless_max_retries=_read_nonnegative_int("FEATHERLESS_MAX_RETRIES", 2),
        risk_weights=risk_weights,
    )