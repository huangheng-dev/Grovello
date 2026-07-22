from io import BytesIO
from typing import Any
from uuid import UUID

import pytest
from botocore.exceptions import ClientError

from grovello.object_storage import (
    AbortMultipartUploadRequest,
    CopyObjectRequest,
    CreateDownloadGrantRequest,
    CreateUploadGrantRequest,
    DeleteObjectRequest,
    StorageObjectRef,
    UploadGrantMethod,
)
from grovello.s3_object_storage import (
    ObjectStorageIntegrityError,
    ObjectStorageOperationError,
    S3EncryptionMode,
    S3ObjectStorage,
    S3ObjectStorageConfig,
)

WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000001")
SHA256 = "a" * 64
CONTENT = b"verified asset content"


class FakeS3Client:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.objects = {
            "workspaces/one/staging/file": {
                "ContentLength": 128,
                "ContentType": "image/png",
                "Metadata": {"sha256": SHA256},
                "ETag": '"etag-source"',
                "VersionId": "version-source",
            }
        }

    def head_bucket(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("head_bucket", kwargs))
        return {}

    def generate_presigned_post(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("generate_presigned_post", kwargs))
        return {"url": "https://public.example.invalid/grovello", "fields": kwargs["Fields"]}

    def generate_presigned_url(self, operation: str, **kwargs: Any) -> str:
        self.calls.append((operation, kwargs))
        return "https://public.example.invalid/grovello/object?signed=true"

    def head_object(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("head_object", kwargs))
        return self.objects[kwargs["Key"]]

    def get_object(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("get_object", kwargs))
        return {"Body": BytesIO(CONTENT)}

    def copy_object(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("copy_object", kwargs))
        source = kwargs["CopySource"]["Key"]
        self.objects[kwargs["Key"]] = {
            **self.objects[source],
            "ETag": '"etag-copy"',
            "VersionId": "version-copy",
        }
        return {}

    def delete_object(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("delete_object", kwargs))
        return {}

    def abort_multipart_upload(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("abort_multipart_upload", kwargs))
        return {}


def storage_config(**overrides: Any) -> S3ObjectStorageConfig:
    values = {
        "endpoint_url": "http://object-storage:9000",
        "public_endpoint_url": "http://localhost:9000",
        "region": "us-east-1",
        "bucket": "grovello",
        "access_key_id": "application-key",
        "secret_access_key": "application-secret",
        "encryption_mode": S3EncryptionMode.NONE,
    }
    values.update(overrides)
    return S3ObjectStorageConfig(**values)


@pytest.mark.asyncio
async def test_presigned_upload_is_exact_and_uses_the_public_endpoint_client() -> None:
    operation_client = FakeS3Client()
    signing_client = FakeS3Client()
    storage = S3ObjectStorage(
        storage_config(encryption_mode=S3EncryptionMode.SSE_S3),
        operation_client=operation_client,
        signing_client=signing_client,
    )
    destination = StorageObjectRef(WORKSPACE_ID, "workspaces/one/staging/file")

    grant = await storage.create_upload_grant(
        CreateUploadGrantRequest(destination, "image/png", 128, SHA256, 1_800)
    )

    assert grant.method == UploadGrantMethod.POST
    assert grant.url.startswith("https://public.example.invalid/")
    assert operation_client.calls == []
    call = signing_client.calls[0][1]
    assert call["Key"] == destination.object_key
    assert ["content-length-range", 128, 128] in call["Conditions"]
    assert call["Fields"]["x-amz-meta-sha256"] == SHA256
    assert call["Fields"]["x-amz-server-side-encryption"] == "AES256"


@pytest.mark.asyncio
async def test_health_head_copy_download_delete_and_abort_use_exact_objects() -> None:
    client = FakeS3Client()
    storage = S3ObjectStorage(storage_config(), operation_client=client, signing_client=client)
    source = StorageObjectRef(WORKSPACE_ID, "workspaces/one/staging/file")
    destination = StorageObjectRef(WORKSPACE_ID, "workspaces/one/assets/file")

    assert (await storage.health()).available is True
    stored = await storage.head_object(source)
    assert stored.checksum_sha256 == SHA256
    copied = await storage.copy_object(CopyObjectRequest(source, destination, SHA256))
    assert copied.location == destination
    grant = await storage.create_download_grant(CreateDownloadGrantRequest(destination, 60))
    assert "signed=true" in grant.url
    await storage.delete_object(DeleteObjectRequest(destination, "version-copy"))
    await storage.abort_multipart_upload(AbortMultipartUploadRequest(source, "upload-id"))

    delete_call = next(kwargs for name, kwargs in client.calls if name == "delete_object")
    assert delete_call == {
        "Bucket": "grovello",
        "Key": destination.object_key,
        "VersionId": "version-copy",
    }
    abort_call = next(kwargs for name, kwargs in client.calls if name == "abort_multipart_upload")
    assert abort_call["Key"] == source.object_key
    assert abort_call["UploadId"] == "upload-id"


@pytest.mark.asyncio
async def test_copy_fails_closed_when_integrity_metadata_does_not_match() -> None:
    client = FakeS3Client()
    storage = S3ObjectStorage(storage_config(), operation_client=client, signing_client=client)
    source = StorageObjectRef(WORKSPACE_ID, "workspaces/one/staging/file")
    destination = StorageObjectRef(WORKSPACE_ID, "workspaces/one/assets/file")

    with pytest.raises(ObjectStorageIntegrityError):
        await storage.copy_object(CopyObjectRequest(source, destination, "b" * 64))

    assert all(name != "copy_object" for name, _kwargs in client.calls)


@pytest.mark.asyncio
async def test_provider_errors_are_classified_without_leaking_request_details() -> None:
    class FailingClient(FakeS3Client):
        def head_bucket(self, **kwargs: Any) -> dict[str, Any]:
            raise ClientError(
                {
                    "Error": {"Code": "ServiceUnavailable", "Message": "secret endpoint detail"},
                    "ResponseMetadata": {"HTTPStatusCode": 503},
                },
                "HeadBucket",
            )

    client = FailingClient()
    storage = S3ObjectStorage(storage_config(), operation_client=client, signing_client=client)
    health = await storage.health()
    assert health.available is False
    assert health.detail == "ServiceUnavailable;retryable=true"
    assert "secret endpoint detail" not in (health.detail or "")

    with pytest.raises(ObjectStorageOperationError) as error:
        await storage._call("health", client.head_bucket, Bucket="grovello")
    assert error.value.retryable is True


def test_kms_encryption_requires_a_key_reference() -> None:
    with pytest.raises(ValueError, match="KMS key ID"):
        storage_config(encryption_mode=S3EncryptionMode.SSE_KMS)


@pytest.mark.asyncio
async def test_calculate_sha256_streams_the_exact_object() -> None:
    import hashlib

    client = FakeS3Client()
    storage = S3ObjectStorage(storage_config(), operation_client=client, signing_client=client)
    source = StorageObjectRef(WORKSPACE_ID, "workspaces/one/staging/file")

    assert await storage.calculate_sha256(source) == hashlib.sha256(CONTENT).hexdigest()
    call = next(kwargs for name, kwargs in client.calls if name == "get_object")
    assert call == {"Bucket": "grovello", "Key": source.object_key}


@pytest.mark.asyncio
async def test_object_chunks_are_streamed_without_whole_object_buffering() -> None:
    client = FakeS3Client()
    storage = S3ObjectStorage(storage_config(), operation_client=client, signing_client=client)
    source = StorageObjectRef(WORKSPACE_ID, "workspaces/one/staging/file")

    streamed = [chunk async for chunk in storage.iter_object_chunks(source, chunk_size=5)]
    assert b"".join(streamed) == CONTENT
    assert all(len(chunk) <= 5 for chunk in streamed)
