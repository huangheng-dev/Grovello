from grovello.config import Settings
from grovello.object_storage import ObjectStorage
from grovello.s3_object_storage import S3EncryptionMode, S3ObjectStorage, S3ObjectStorageConfig


def build_object_storage(settings: Settings) -> ObjectStorage | None:
    if not settings.object_storage_configured:
        return None
    assert settings.object_storage_access_key_id is not None
    assert settings.object_storage_secret_access_key is not None
    return S3ObjectStorage(
        S3ObjectStorageConfig(
            endpoint_url=str(settings.object_storage_endpoint).rstrip("/"),
            public_endpoint_url=str(settings.object_storage_public_endpoint).rstrip("/"),
            region=settings.object_storage_region,
            bucket=settings.object_storage_bucket,
            access_key_id=settings.object_storage_access_key_id.get_secret_value(),
            secret_access_key=settings.object_storage_secret_access_key.get_secret_value(),
            force_path_style=settings.object_storage_force_path_style,
            encryption_mode=S3EncryptionMode(settings.object_storage_sse_mode),
            kms_key_id=settings.object_storage_kms_key_id,
            connect_timeout_seconds=settings.object_storage_connect_timeout_seconds,
            read_timeout_seconds=settings.object_storage_read_timeout_seconds,
        )
    )
