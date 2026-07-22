import hashlib
import os
import uuid
from uuid import UUID

import httpx
import pytest

from grovello.object_storage import (
    CopyObjectRequest,
    CreateDownloadGrantRequest,
    CreateUploadGrantRequest,
    DeleteObjectRequest,
    StorageObjectRef,
)
from grovello.s3_object_storage import S3EncryptionMode, S3ObjectStorage, S3ObjectStorageConfig


@pytest.mark.asyncio
async def test_minio_signed_upload_promotion_download_and_exact_cleanup() -> None:
    endpoint = os.getenv("GROVELLO_TEST_S3_ENDPOINT")
    access_key = os.getenv("GROVELLO_TEST_S3_ACCESS_KEY_ID")
    secret_key = os.getenv("GROVELLO_TEST_S3_SECRET_ACCESS_KEY")
    if not endpoint or not access_key or not secret_key:
        pytest.skip("Local S3-compatible integration environment is not configured")

    bucket = os.getenv("GROVELLO_TEST_S3_BUCKET", "grovello")
    storage = S3ObjectStorage(
        S3ObjectStorageConfig(
            endpoint_url=endpoint,
            public_endpoint_url=endpoint,
            region="us-east-1",
            bucket=bucket,
            access_key_id=access_key,
            secret_access_key=secret_key,
            encryption_mode=S3EncryptionMode.NONE,
        )
    )
    assert (await storage.health()).available is True

    workspace_id = UUID("00000000-0000-4000-8000-000000000001")
    nonce = uuid.uuid4().hex
    source = StorageObjectRef(workspace_id, f"workspaces/{workspace_id}/staging/{nonce}")
    destination = StorageObjectRef(workspace_id, f"workspaces/{workspace_id}/assets/{nonce}")
    content = b"Grovello governed asset storage integration test"
    checksum = hashlib.sha256(content).hexdigest()

    upload = await storage.create_upload_grant(
        CreateUploadGrantRequest(source, "image/png", len(content), checksum, 300)
    )
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            upload.url,
            data=upload.fields,
            files={"file": ("fixture.png", content, "image/png")},
        )
        assert response.status_code in {200, 204}

    source_object = await storage.head_object(source)
    assert source_object.checksum_sha256 == checksum
    assert await storage.calculate_sha256(source) == checksum
    destination_object = await storage.copy_object(
        CopyObjectRequest(source, destination, checksum, source_object.provider_version_id)
    )
    download = await storage.create_download_grant(CreateDownloadGrantRequest(destination, 60))
    async with httpx.AsyncClient(timeout=10) as client:
        downloaded = await client.get(download.url)
        assert downloaded.status_code == 200
        assert downloaded.content == content

    assert destination_object.provider_version_id is not None
    assert source_object.provider_version_id is not None
    await storage.delete_object(
        DeleteObjectRequest(destination, destination_object.provider_version_id)
    )
    await storage.delete_object(DeleteObjectRequest(source, source_object.provider_version_id))
