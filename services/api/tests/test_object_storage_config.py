from pathlib import Path

import pytest
from pydantic import ValidationError

from grovello.config import Settings

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_object_storage_credentials_are_paired_and_redacted() -> None:
    unconfigured = Settings(
        _env_file=None,
        object_storage_access_key_id="",
        object_storage_secret_access_key="",
    )
    assert unconfigured.object_storage_configured is False

    settings = Settings(
        _env_file=None,
        object_storage_access_key_id="application-key",
        object_storage_secret_access_key="sensitive-secret",
    )
    assert settings.object_storage_configured is True
    assert settings.object_storage_secret_access_key is not None
    assert settings.object_storage_secret_access_key.get_secret_value() == "sensitive-secret"
    assert "sensitive-secret" not in repr(settings)

    with pytest.raises(ValidationError, match="must be set together"):
        Settings(_env_file=None, object_storage_access_key_id="application-key")


def test_production_object_storage_requires_tls_and_encryption_when_configured() -> None:
    credentials = {
        "object_storage_access_key_id": "application-key",
        "object_storage_secret_access_key": "sensitive-secret",
    }
    with pytest.raises(ValidationError, match="cannot be disabled"):
        Settings(
            _env_file=None,
            environment="production",
            object_storage_endpoint="https://storage.example.com",
            object_storage_sse_mode="none",
            **credentials,
        )
    with pytest.raises(ValidationError, match="must use HTTPS"):
        Settings(
            _env_file=None,
            environment="production",
            object_storage_endpoint="http://storage.example.com",
            object_storage_sse_mode="sse-s3",
            **credentials,
        )
    with pytest.raises(ValidationError, match="public endpoint must use HTTPS"):
        Settings(
            _env_file=None,
            environment="production",
            object_storage_endpoint="https://storage.internal.example.com",
            object_storage_public_endpoint="http://storage.example.com",
            object_storage_sse_mode="sse-s3",
            **credentials,
        )


def test_kms_and_signed_grant_settings_are_bounded() -> None:
    with pytest.raises(ValidationError, match="KMS key ID"):
        Settings(_env_file=None, object_storage_sse_mode="sse-kms")
    with pytest.raises(ValidationError, match="download TTL"):
        Settings(_env_file=None, asset_download_ttl_seconds=7_200)
    with pytest.raises(ValidationError, match="DNS-compatible"):
        Settings(_env_file=None, object_storage_bucket='grovello"}]}')
    with pytest.raises(ValidationError, match="stream limit"):
        Settings(_env_file=None, asset_max_upload_bytes=100, asset_scanner_max_stream_bytes=99)


def test_production_storage_requires_a_scanner() -> None:
    with pytest.raises(ValidationError, match="scanner must be configured"):
        Settings(
            _env_file=None,
            environment="production",
            object_storage_endpoint="https://storage.internal.example.com",
            object_storage_public_endpoint="https://storage.example.com",
            object_storage_access_key_id="application-key",
            object_storage_secret_access_key="sensitive-secret",
        )


def test_local_object_storage_cors_uses_exact_configurable_origins() -> None:
    compose = (REPOSITORY_ROOT / "compose.platform.yaml").read_text(encoding="utf-8")
    example_environment = (REPOSITORY_ROOT / ".env.example").read_text(encoding="utf-8")

    assert "MINIO_API_CORS_ALLOW_ORIGIN" in compose
    assert "MINIO_API_CORS_ALLOW_CREDENTIALS_WITH_WILDCARD: \"off\"" in compose
    assert "GROVELLO_OBJECT_STORAGE_CORS_ALLOWED_ORIGINS" in compose
    assert "GROVELLO_OBJECT_STORAGE_CORS_ALLOWED_ORIGINS" in example_environment
    cors_line = next(
        line
        for line in example_environment.splitlines()
        if line.startswith("GROVELLO_OBJECT_STORAGE_CORS_ALLOWED_ORIGINS=")
    )
    assert "http://127.0.0.1:3200" in cors_line
    assert "*" not in cors_line
