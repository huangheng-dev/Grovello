from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from grovello.asset_uploads import UploadMutationContext
from grovello.models import AssetBlob, AssetVersionFile, AuditEvent, BusinessObject, BusinessObjectVersion
from grovello.object_storage import (
    CreateDownloadGrantRequest,
    DownloadGrant,
    ObjectStorage,
    StorageObjectRef,
)


class AssetDownloadNotFoundError(RuntimeError):
    pass


class AssetDownloadDeniedError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AssetDownloadResult:
    asset_id: UUID
    asset_version_id: UUID
    blob_id: UUID
    filename: str
    content_type: str
    byte_size: int
    sha256: str
    grant: DownloadGrant


class SqlAlchemyAssetDownloadStore:
    def __init__(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        storage: ObjectStorage,
        ttl_seconds: int,
    ) -> None:
        self._session = session
        self._workspace_id = workspace_id
        self._storage = storage
        self._ttl_seconds = ttl_seconds

    async def authorize(
        self,
        asset_id: UUID,
        asset_version_id: UUID,
        context: UploadMutationContext,
    ) -> AssetDownloadResult:
        asset = await self._session.scalar(
            select(BusinessObject).where(
                BusinessObject.workspace_id == self._workspace_id,
                BusinessObject.id == asset_id,
                BusinessObject.object_type == "asset",
            )
        )
        if asset is None:
            raise AssetDownloadNotFoundError("Asset was not found")
        version = await self._session.scalar(
            select(BusinessObjectVersion).where(
                BusinessObjectVersion.workspace_id == self._workspace_id,
                BusinessObjectVersion.id == asset_version_id,
                BusinessObjectVersion.object_id == asset_id,
            )
        )
        if version is None:
            raise AssetDownloadNotFoundError("Asset version was not found")
        if asset.status != "active" or version.status != "active":
            raise AssetDownloadDeniedError("Only an approved active asset version can be downloaded")
        binding = await self._session.scalar(
            select(AssetVersionFile).where(
                AssetVersionFile.workspace_id == self._workspace_id,
                AssetVersionFile.business_object_version_id == asset_version_id,
                AssetVersionFile.role == "original",
                AssetVersionFile.variant_key == "default",
            )
        )
        if binding is None:
            raise AssetDownloadNotFoundError("Asset original file was not found")
        blob = await self._session.scalar(
            select(AssetBlob).where(
                AssetBlob.workspace_id == self._workspace_id,
                AssetBlob.id == binding.blob_id,
            )
        )
        if blob is None:
            raise AssetDownloadNotFoundError("Asset blob was not found")
        if blob.scan_status != "clean" or blob.storage_status != "available":
            raise AssetDownloadDeniedError("Asset blob is not safe and available for download")

        self._session.add(
            AuditEvent(
                id=uuid4(), workspace_id=self._workspace_id, actor_type=context.actor_type,
                actor_id=context.actor_id, session_id=context.session_id, request_id=context.request_id,
                action="asset.download.request_authorized", resource_type="asset",
                resource_id=str(asset_id), outcome="succeeded",
                reason="Issue a bounded private download grant",
                evidence={
                    "assetVersionId": str(asset_version_id),
                    "blobId": str(blob.id),
                    "expiresInSeconds": self._ttl_seconds,
                },
            )
        )
        await self._session.commit()
        grant = await self._storage.create_download_grant(
            CreateDownloadGrantRequest(
                source=StorageObjectRef(self._workspace_id, blob.object_key),
                expires_in_seconds=self._ttl_seconds,
            )
        )
        return AssetDownloadResult(
            asset_id=asset_id,
            asset_version_id=asset_version_id,
            blob_id=blob.id,
            filename=str(version.payload.get("originalFilename", version.name)),
            content_type=blob.detected_mime_type,
            byte_size=blob.byte_size,
            sha256=blob.sha256,
            grant=grant,
        )
