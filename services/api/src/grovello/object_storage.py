from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable
from uuid import UUID


class UploadGrantMethod(StrEnum):
    POST = "POST"
    PUT = "PUT"
    MULTIPART = "MULTIPART"


@dataclass(frozen=True, slots=True)
class StorageObjectRef:
    workspace_id: UUID
    object_key: str
    storage_profile: str = "default"

    def __post_init__(self) -> None:
        segments = self.object_key.split("/")
        if (
            not self.object_key
            or self.object_key.startswith("/")
            or "\\" in self.object_key
            or any(segment in {"", ".", ".."} for segment in segments)
        ):
            raise ValueError("Object key must be a normalized relative key")
        if not self.storage_profile:
            raise ValueError("Storage profile is required")


@dataclass(frozen=True, slots=True)
class CreateUploadGrantRequest:
    destination: StorageObjectRef
    content_type: str
    content_length: int
    checksum_sha256: str
    expires_in_seconds: int

    def __post_init__(self) -> None:
        if not self.content_type:
            raise ValueError("Content type is required")
        if self.content_length <= 0:
            raise ValueError("Content length must be positive")
        _validate_sha256(self.checksum_sha256)
        _validate_expiry(self.expires_in_seconds)


@dataclass(frozen=True, slots=True)
class UploadGrant:
    method: UploadGrantMethod
    url: str
    expires_at: datetime
    fields: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StoredObject:
    location: StorageObjectRef
    byte_size: int
    content_type: str
    checksum_sha256: str
    etag: str | None = None
    provider_version_id: str | None = None

    def __post_init__(self) -> None:
        if self.byte_size <= 0:
            raise ValueError("Stored object size must be positive")
        _validate_sha256(self.checksum_sha256)


@dataclass(frozen=True, slots=True)
class CopyObjectRequest:
    source: StorageObjectRef
    destination: StorageObjectRef
    expected_sha256: str
    expected_provider_version_id: str | None = None

    def __post_init__(self) -> None:
        if self.source.workspace_id != self.destination.workspace_id:
            raise ValueError("Object promotion cannot cross workspace boundaries")
        if self.source == self.destination:
            raise ValueError("Object promotion requires a distinct destination")
        _validate_sha256(self.expected_sha256)


@dataclass(frozen=True, slots=True)
class DownloadGrant:
    url: str
    expires_at: datetime
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CreateDownloadGrantRequest:
    source: StorageObjectRef
    expires_in_seconds: int

    def __post_init__(self) -> None:
        _validate_expiry(self.expires_in_seconds)


@dataclass(frozen=True, slots=True)
class DeleteObjectRequest:
    target: StorageObjectRef
    expected_provider_version_id: str | None = None


@dataclass(frozen=True, slots=True)
class AbortMultipartUploadRequest:
    target: StorageObjectRef
    upload_id: str

    def __post_init__(self) -> None:
        if not self.upload_id:
            raise ValueError("Multipart upload ID is required")


@dataclass(frozen=True, slots=True)
class ObjectStorageHealth:
    available: bool
    provider: str
    detail: str | None = None


@runtime_checkable
class ObjectStorage(Protocol):
    """Provider-neutral private object-storage boundary.

    Authorization, approval, and audit are application-service concerns. Implementations receive
    exact tenant-scoped object references and must never expose long-lived storage credentials.
    """

    async def health(self) -> ObjectStorageHealth: ...

    async def create_upload_grant(self, request: CreateUploadGrantRequest) -> UploadGrant:
        """Constrain a short-lived grant to the exact key, size, type, and SHA-256 checksum."""
        ...

    async def head_object(self, location: StorageObjectRef) -> StoredObject:
        """Read verified provider metadata without returning object bytes."""
        ...

    async def calculate_sha256(self, location: StorageObjectRef) -> str:
        """Stream one exact object and calculate its content SHA-256 without buffering it whole."""
        ...

    def iter_object_chunks(
        self, location: StorageObjectRef, *, chunk_size: int = 1024 * 1024
    ) -> AsyncIterator[bytes]:
        """Stream one exact private object in bounded chunks."""
        ...

    async def copy_object(self, request: CopyObjectRequest) -> StoredObject:
        """Promote one exact tenant object to a distinct immutable destination."""
        ...

    async def create_download_grant(self, request: CreateDownloadGrantRequest) -> DownloadGrant:
        """Grant short-lived access to one authorized private object."""
        ...

    async def delete_object(self, request: DeleteObjectRequest) -> None:
        """Delete one exact object; prefix and bucket-wide deletion are outside this contract."""
        ...

    async def abort_multipart_upload(self, request: AbortMultipartUploadRequest) -> None:
        """Abort one exact multipart upload without scanning or deleting adjacent keys."""
        ...


def _validate_sha256(value: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError("SHA-256 must be 64 lowercase hexadecimal characters")


def _validate_expiry(value: int) -> None:
    if value <= 0 or value > 3600:
        raise ValueError("Signed grant expiry must be between 1 and 3600 seconds")
