from functools import lru_cache
import os
from pydantic import BaseModel

class Settings(BaseModel):
    app_name: str = "Agent Reliability Lab"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./agent_reliability_lab.db"

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(app_name=os.getenv("APP_NAME", "Agent Reliability Lab"), app_env=os.getenv("APP_ENV", "development"), api_v1_prefix=os.getenv("API_V1_PREFIX", "/api/v1"), database_url=os.getenv("DATABASE_URL", "sqlite:///./agent_reliability_lab.db"))

@lru_cache
def get_settings() -> Settings:
    return Settings.from_environment()
