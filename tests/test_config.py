import importlib
from pathlib import Path

import pytest

import config
from config import get_settings


def test_demo_mode_defaults_off(monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)

    assert get_settings().demo_mode is False


def test_settings_parse_environment_values(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example, https://admin.example")
    monkeypatch.setenv("RATE_LIMIT", "12")
    monkeypatch.setenv("RETENTION_DAYS", "7")

    settings = get_settings()

    assert settings.demo_mode is False
    assert settings.cors_origins == ("https://app.example", "https://admin.example")
    assert settings.rate_limit_per_minute == 12
    assert settings.retention_days == 7


def test_settings_reject_invalid_boolean_and_nonpositive_limit(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "sometimes")
    with pytest.raises(ValueError, match="DEMO_MODE"):
        get_settings()

    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("RATE_LIMIT", "0")
    with pytest.raises(ValueError, match="RATE_LIMIT"):
        get_settings()


def test_project_root_env_is_loaded_when_working_directory_changes(monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(repo_root.parent)
    monkeypatch.delenv("FEATHERLESS_MODEL", raising=False)

    importlib.reload(config)
    settings = config.get_settings()

    assert settings.featherless_model == "Qwen/Qwen3.5-27B"