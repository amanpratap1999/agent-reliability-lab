from functools import lru_cache
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

class Settings(BaseModel):
    app_name: str = "Agent Reliability Lab"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./agent_reliability_lab.db"
    log_level: LogLevel = "INFO"
    artifact_dir: Path = Path("./artifacts")

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return str(value).strip().upper()

    @field_validator("api_v1_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        value = value.strip()
        if not value.startswith("/"):
            raise ValueError("API_V1_PREFIX must start with '/'")
        return value.rstrip("/") or "/"

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("DATABASE_URL cannot be blank")
        return value

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            app_name=os.getenv("APP_NAME", "Agent Reliability Lab"),
            app_env=os.getenv("APP_ENV", "development"),
            api_v1_prefix=os.getenv("API_V1_PREFIX", "/api/v1"),
            database_url=os.getenv("DATABASE_URL", "sqlite:///./agent_reliability_lab.db"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            artifact_dir=Path(os.getenv("ARTIFACT_DIR", "./artifacts")),
        )

@lru_cache
def get_settings() -> Settings:
    return Settings.from_environment()
