import json
import logging

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.logging import SecretRedactionFilter, StructuredJsonFormatter


def test_settings_load_environment_overrides(monkeypatch):
    monkeypatch.setenv("APP_NAME", "Test Lab")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("API_V1_PREFIX", "/v2/")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("ARTIFACT_DIR", "./test-artifacts")

    settings = Settings.from_environment()
    assert settings.app_name == "Test Lab"
    assert settings.app_env == "test"
    assert settings.api_v1_prefix == "/v2"
    assert settings.database_url == "sqlite:///./test.db"
    assert settings.log_level == "DEBUG"
    assert str(settings.artifact_dir) == "test-artifacts"


def test_invalid_log_level_is_rejected():
    with pytest.raises(ValidationError):
        Settings(log_level="TRACE")


def test_invalid_database_url_is_rejected():
    with pytest.raises(ValidationError):
        Settings(database_url="   ")


def test_structured_logging_redacts_credentials():
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="authorization=Bearer abc123 api_key=key123 password=hunter2", args=(), exc_info=None,
    )
    assert SecretRedactionFilter().filter(record) is True
    rendered = StructuredJsonFormatter().format(record)
    payload = json.loads(rendered)
    assert payload["level"] == "INFO"
    assert "abc123" not in rendered
    assert "key123" not in rendered
    assert "hunter2" not in rendered
    assert rendered.count("[REDACTED]") == 3
