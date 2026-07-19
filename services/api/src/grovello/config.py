from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="GROVELLO_", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    api_title: str = "Grovello API"
    api_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://grovello:grovello@localhost:5432/grovello"
    valkey_url: str = "redis://localhost:6379/0"
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "grovello-growth"
    allowed_origins: list[AnyHttpUrl | str] = Field(default_factory=lambda: ["http://localhost:3000"])

    @property
    def origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.allowed_origins]


@lru_cache
def get_settings() -> Settings:
    return Settings()
