import re
from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
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
    object_storage_endpoint: AnyHttpUrl | str = "http://localhost:9000"
    object_storage_public_endpoint: AnyHttpUrl | str = "http://localhost:9000"
    object_storage_region: str = "us-east-1"
    object_storage_bucket: str = "grovello"
    object_storage_access_key_id: SecretStr | None = None
    object_storage_secret_access_key: SecretStr | None = None
    object_storage_force_path_style: bool = True
    object_storage_sse_mode: Literal["none", "sse-s3", "sse-kms"] = "sse-s3"
    object_storage_kms_key_id: str | None = None
    object_storage_connect_timeout_seconds: float = 5.0
    object_storage_read_timeout_seconds: float = 30.0
    asset_max_upload_bytes: int = 104_857_600
    asset_upload_ttl_seconds: int = 1_800
    asset_download_ttl_seconds: int = 60
    asset_scanner_provider: Literal["clamav"] = "clamav"
    asset_scanner_host: str | None = None
    asset_scanner_port: int = 3310
    asset_scanner_connect_timeout_seconds: float = 5.0
    asset_scanner_timeout_seconds: float = 120.0
    asset_scanner_max_stream_bytes: int = 104_857_600
    import_max_source_bytes: int = 26_214_400
    import_upload_ttl_seconds: int = 1_800
    import_max_rows: int = 10_000
    import_max_columns: int = 100
    import_max_scalar_bytes: int = 65_536
    import_max_json_depth: int = 12
    import_preview_rows: int = 50

    @field_validator(
        "object_storage_access_key_id",
        "object_storage_secret_access_key",
        "asset_scanner_host",
        mode="before",
    )
    @classmethod
    def normalize_empty_storage_credentials(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def validate_object_storage(self) -> "Settings":
        if (
            not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", self.object_storage_bucket)
            or ".." in self.object_storage_bucket
        ):
            raise ValueError("Object storage bucket must be a normalized DNS-compatible name")
        access_key_set = self.object_storage_access_key_id is not None
        secret_key_set = self.object_storage_secret_access_key is not None
        if access_key_set != secret_key_set:
            raise ValueError("Object storage access key ID and secret access key must be set together")
        if self.object_storage_sse_mode == "sse-kms" and not self.object_storage_kms_key_id:
            raise ValueError("Object storage KMS key ID is required for sse-kms")
        if self.environment == "production" and self.object_storage_configured:
            if self.object_storage_sse_mode == "none":
                raise ValueError("Object storage encryption cannot be disabled in production")
            if not str(self.object_storage_endpoint).startswith("https://"):
                raise ValueError("Object storage endpoint must use HTTPS in production")
            if not str(self.object_storage_public_endpoint).startswith("https://"):
                raise ValueError("Object storage public endpoint must use HTTPS in production")
        if self.asset_max_upload_bytes <= 0:
            raise ValueError("Asset maximum upload size must be positive")
        if not 1 <= self.asset_scanner_port <= 65535:
            raise ValueError("Asset scanner port is invalid")
        if self.asset_scanner_connect_timeout_seconds <= 0 or self.asset_scanner_timeout_seconds <= 0:
            raise ValueError("Asset scanner timeouts must be positive")
        if self.asset_scanner_max_stream_bytes < self.asset_max_upload_bytes:
            raise ValueError("Asset scanner stream limit cannot be smaller than the upload limit")
        if self.import_max_source_bytes <= 0:
            raise ValueError("Import maximum source size must be positive")
        if self.asset_scanner_max_stream_bytes < self.import_max_source_bytes:
            raise ValueError("Asset scanner stream limit cannot be smaller than the import source limit")
        for value, name, maximum in (
            (self.import_max_rows, "Import row limit", 100_000),
            (self.import_max_columns, "Import column limit", 1_000),
            (self.import_max_scalar_bytes, "Import scalar byte limit", 1_048_576),
            (self.import_max_json_depth, "Import JSON depth limit", 32),
            (self.import_preview_rows, "Import preview row limit", 500),
        ):
            if value <= 0 or value > maximum:
                raise ValueError(f"{name} must be between 1 and {maximum}")
        if (
            self.environment == "production"
            and self.object_storage_configured
            and not self.asset_scanner_configured
        ):
            raise ValueError("Asset scanner must be configured with object storage in production")
        for value, name in (
            (self.asset_upload_ttl_seconds, "Asset upload TTL"),
            (self.asset_download_ttl_seconds, "Asset download TTL"),
            (self.import_upload_ttl_seconds, "Import upload TTL"),
        ):
            if value <= 0 or value > 3_600:
                raise ValueError(f"{name} must be between 1 and 3600 seconds")
        return self

    @property
    def origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.allowed_origins]

    @property
    def object_storage_configured(self) -> bool:
        return (
            self.object_storage_access_key_id is not None
            and self.object_storage_secret_access_key is not None
        )

    @property
    def asset_scanner_configured(self) -> bool:
        return self.asset_scanner_host is not None


@lru_cache
def get_settings() -> Settings:
    return Settings()
