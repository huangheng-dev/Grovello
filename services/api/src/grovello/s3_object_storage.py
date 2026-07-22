import asyncio
import hashlib
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, NoReturn, TypeVar

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from grovello.object_storage import (
    AbortMultipartUploadRequest,
    CopyObjectRequest,
    CreateDownloadGrantRequest,
    CreateUploadGrantRequest,
    DeleteObjectRequest,
    DownloadGrant,
    ObjectStorageHealth,
    StorageObjectRef,
    StoredObject,
    UploadGrant,
    UploadGrantMethod,
)

Result = TypeVar("Result")


class S3EncryptionMode(StrEnum):
    NONE = "none"
    SSE_S3 = "sse-s3"
    SSE_KMS = "sse-kms"


@dataclass(frozen=True, slots=True)
class S3ObjectStorageConfig:
    endpoint_url: str
    public_endpoint_url: str
    region: str
    bucket: str
    access_key_id: str
    secret_access_key: str
    force_path_style: bool = True
    encryption_mode: S3EncryptionMode = S3EncryptionMode.SSE_S3
    kms_key_id: str | None = None
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        required = {
            "endpoint URL": self.endpoint_url,
            "public endpoint URL": self.public_endpoint_url,
            "region": self.region,
            "bucket": self.bucket,
            "access key ID": self.access_key_id,
            "secret access key": self.secret_access_key,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"Missing S3-compatible storage configuration: {', '.join(missing)}")
        if self.encryption_mode == S3EncryptionMode.SSE_KMS and not self.kms_key_id:
            raise ValueError("KMS key ID is required for sse-kms")
        if self.connect_timeout_seconds <= 0 or self.read_timeout_seconds <= 0:
            raise ValueError("Object storage timeouts must be positive")


class ObjectStorageOperationError(RuntimeError):
    def __init__(self, operation: str, code: str, *, retryable: bool) -> None:
        super().__init__(f"Object storage {operation} failed ({code})")
        self.operation = operation
        self.code = code
        self.retryable = retryable


class ObjectStorageIntegrityError(ObjectStorageOperationError):
    def __init__(self, operation: str, code: str = "integrity_mismatch") -> None:
        super().__init__(operation, code, retryable=False)


class S3ObjectStorage:
    """S3-compatible implementation with bounded calls and no provider credentials in results."""

    def __init__(
        self,
        config: S3ObjectStorageConfig,
        *,
        operation_client: Any | None = None,
        signing_client: Any | None = None,
    ) -> None:
        self._config = config
        client_config = Config(
            signature_version="s3v4",
            connect_timeout=config.connect_timeout_seconds,
            read_timeout=config.read_timeout_seconds,
            retries={"max_attempts": 3, "mode": "standard"},
            s3={"addressing_style": "path" if config.force_path_style else "auto"},
        )
        common = {
            "service_name": "s3",
            "region_name": config.region,
            "aws_access_key_id": config.access_key_id,
            "aws_secret_access_key": config.secret_access_key,
            "config": client_config,
        }
        self._operation_client = operation_client or boto3.client(
            endpoint_url=config.endpoint_url,
            **common,
        )
        self._signing_client = signing_client or boto3.client(
            endpoint_url=config.public_endpoint_url,
            **common,
        )

    async def health(self) -> ObjectStorageHealth:
        try:
            await self._call("health", self._operation_client.head_bucket, Bucket=self._config.bucket)
        except ObjectStorageOperationError as error:
            return ObjectStorageHealth(
                available=False,
                provider="s3-compatible",
                detail=f"{error.code};retryable={str(error.retryable).lower()}",
            )
        return ObjectStorageHealth(available=True, provider="s3-compatible")

    async def create_upload_grant(self, request: CreateUploadGrantRequest) -> UploadGrant:
        fields = {
            "Content-Type": request.content_type,
            "x-amz-meta-sha256": request.checksum_sha256,
            **self._presigned_encryption_fields(),
        }
        conditions: list[Any] = [
            {"Content-Type": request.content_type},
            {"x-amz-meta-sha256": request.checksum_sha256},
            ["content-length-range", request.content_length, request.content_length],
            *[{key: value} for key, value in self._presigned_encryption_fields().items()],
        ]
        try:
            response = self._signing_client.generate_presigned_post(
                Bucket=self._config.bucket,
                Key=request.destination.object_key,
                Fields=fields,
                Conditions=conditions,
                ExpiresIn=request.expires_in_seconds,
            )
        except (ClientError, BotoCoreError) as error:
            self._raise_operation_error("create_upload_grant", error)
        return UploadGrant(
            method=UploadGrantMethod.POST,
            url=response["url"],
            fields=response["fields"],
            expires_at=datetime.now(UTC) + timedelta(seconds=request.expires_in_seconds),
        )

    async def head_object(self, location: StorageObjectRef) -> StoredObject:
        response = await self._call(
            "head_object",
            self._operation_client.head_object,
            Bucket=self._config.bucket,
            Key=location.object_key,
        )
        checksum = response.get("Metadata", {}).get("sha256")
        if not checksum:
            raise ObjectStorageIntegrityError("head_object", "missing_sha256_metadata")
        return StoredObject(
            location=location,
            byte_size=response["ContentLength"],
            content_type=response.get("ContentType", "application/octet-stream"),
            checksum_sha256=checksum,
            etag=response.get("ETag", "").strip('"') or None,
            provider_version_id=response.get("VersionId"),
        )

    async def calculate_sha256(self, location: StorageObjectRef) -> str:
        return await self._call(
            "calculate_sha256",
            self._calculate_sha256_sync,
            Bucket=self._config.bucket,
            Key=location.object_key,
        )

    def _calculate_sha256_sync(self, **kwargs: Any) -> str:
        response = self._operation_client.get_object(**kwargs)
        body = response["Body"]
        digest = hashlib.sha256()
        try:
            while chunk := body.read(1024 * 1024):
                digest.update(chunk)
        finally:
            body.close()
        return digest.hexdigest()

    async def iter_object_chunks(
        self, location: StorageObjectRef, *, chunk_size: int = 1024 * 1024
    ) -> AsyncIterator[bytes]:
        if chunk_size <= 0:
            raise ValueError("Object stream chunk size must be positive")
        try:
            response = await asyncio.to_thread(
                self._operation_client.get_object,
                Bucket=self._config.bucket,
                Key=location.object_key,
            )
            body = response["Body"]
            try:
                while chunk := await asyncio.to_thread(body.read, chunk_size):
                    yield chunk
            finally:
                await asyncio.to_thread(body.close)
        except (ClientError, BotoCoreError) as error:
            self._raise_operation_error("stream_object", error)

    async def copy_object(self, request: CopyObjectRequest) -> StoredObject:
        source = await self.head_object(request.source)
        if source.checksum_sha256 != request.expected_sha256:
            raise ObjectStorageIntegrityError("copy_object")
        if (
            request.expected_provider_version_id is not None
            and source.provider_version_id != request.expected_provider_version_id
        ):
            raise ObjectStorageIntegrityError("copy_object", "provider_version_mismatch")

        copy_source: dict[str, str] = {
            "Bucket": self._config.bucket,
            "Key": request.source.object_key,
        }
        if source.provider_version_id:
            copy_source["VersionId"] = source.provider_version_id
        await self._call(
            "copy_object",
            self._operation_client.copy_object,
            Bucket=self._config.bucket,
            Key=request.destination.object_key,
            CopySource=copy_source,
            MetadataDirective="COPY",
            **self._api_encryption_args(),
        )
        destination = await self.head_object(request.destination)
        if destination.checksum_sha256 != request.expected_sha256:
            raise ObjectStorageIntegrityError("copy_object")
        return destination

    async def create_download_grant(self, request: CreateDownloadGrantRequest) -> DownloadGrant:
        try:
            url = self._signing_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._config.bucket, "Key": request.source.object_key},
                ExpiresIn=request.expires_in_seconds,
            )
        except (ClientError, BotoCoreError) as error:
            self._raise_operation_error("create_download_grant", error)
        return DownloadGrant(
            url=url,
            expires_at=datetime.now(UTC) + timedelta(seconds=request.expires_in_seconds),
        )

    async def delete_object(self, request: DeleteObjectRequest) -> None:
        parameters = {"Bucket": self._config.bucket, "Key": request.target.object_key}
        if request.expected_provider_version_id:
            parameters["VersionId"] = request.expected_provider_version_id
        await self._call("delete_object", self._operation_client.delete_object, **parameters)

    async def abort_multipart_upload(self, request: AbortMultipartUploadRequest) -> None:
        await self._call(
            "abort_multipart_upload",
            self._operation_client.abort_multipart_upload,
            Bucket=self._config.bucket,
            Key=request.target.object_key,
            UploadId=request.upload_id,
        )

    async def _call(self, operation: str, function: Callable[..., Result], **kwargs: Any) -> Result:
        try:
            return await asyncio.to_thread(function, **kwargs)
        except (ClientError, BotoCoreError) as error:
            self._raise_operation_error(operation, error)

    def _raise_operation_error(
        self,
        operation: str,
        error: ClientError | BotoCoreError,
    ) -> NoReturn:
        if isinstance(error, ClientError):
            response = error.response
            code = str(response.get("Error", {}).get("Code", "client_error"))
            status = int(response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0))
            retryable = status >= 500 or code in {
                "RequestTimeout",
                "SlowDown",
                "Throttling",
                "InternalError",
                "ServiceUnavailable",
            }
            raise ObjectStorageOperationError(operation, code, retryable=retryable) from error
        raise ObjectStorageOperationError(
            operation,
            error.__class__.__name__,
            retryable=True,
        ) from error

    def _api_encryption_args(self) -> dict[str, str]:
        if self._config.encryption_mode == S3EncryptionMode.NONE:
            return {}
        if self._config.encryption_mode == S3EncryptionMode.SSE_S3:
            return {"ServerSideEncryption": "AES256"}
        return {
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": self._config.kms_key_id or "",
        }

    def _presigned_encryption_fields(self) -> dict[str, str]:
        if self._config.encryption_mode == S3EncryptionMode.NONE:
            return {}
        if self._config.encryption_mode == S3EncryptionMode.SSE_S3:
            return {"x-amz-server-side-encryption": "AES256"}
        return {
            "x-amz-server-side-encryption": "aws:kms",
            "x-amz-server-side-encryption-aws-kms-key-id": self._config.kms_key_id or "",
        }
