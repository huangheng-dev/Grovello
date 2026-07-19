from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="GROVELLO_", extra="ignore")
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "grovello-growth"


@lru_cache
def get_settings() -> WorkerSettings:
    return WorkerSettings()
