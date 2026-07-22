from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from grovello.models import AssetBlob, AssetVersionFile, BusinessObject, BusinessObjectVersion


class AssetCatalogNotFoundError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AssetFileRecord:
    blob_id: UUID
    filename: str
    content_type: str
    byte_size: int
    sha256: str
    scan_status: str
    storage_status: str


@dataclass(frozen=True, slots=True)
class AssetVersionRecord:
    id: UUID
    version: int
    name: str
    status: str
    locale: str
    payload: dict
    change_summary: str
    created_at: datetime
    original_file: AssetFileRecord | None
    downloadable: bool


@dataclass(frozen=True, slots=True)
class AssetCatalogRecord:
    id: UUID
    slug: str
    name: str
    status: str
    current_version: int
    updated_at: datetime
    versions: tuple[AssetVersionRecord, ...]


class AssetCatalogStore(Protocol):
    async def list_assets(self, limit: int) -> tuple[AssetCatalogRecord, ...]: ...

    async def get_asset(self, asset_id: UUID, version_limit: int) -> AssetCatalogRecord: ...


class SqlAlchemyAssetCatalogStore:
    def __init__(self, session: AsyncSession, workspace_id: UUID) -> None:
        self._session = session
        self._workspace_id = workspace_id

    async def list_assets(self, limit: int) -> tuple[AssetCatalogRecord, ...]:
        rows = (
            await self._session.execute(
                select(BusinessObject, BusinessObjectVersion)
                .join(
                    BusinessObjectVersion,
                    and_(
                        BusinessObjectVersion.workspace_id == BusinessObject.workspace_id,
                        BusinessObjectVersion.object_id == BusinessObject.id,
                        BusinessObjectVersion.version == BusinessObject.current_version,
                    ),
                )
                .where(
                    BusinessObject.workspace_id == self._workspace_id,
                    BusinessObject.object_type == "asset",
                )
                .order_by(BusinessObject.updated_at.desc(), BusinessObject.id)
                .limit(limit)
            )
        ).all()
        files = await self._original_files([version.id for _, version in rows])
        return tuple(
            self._catalog_record(asset, (self._version_record(asset, version, files),))
            for asset, version in rows
        )

    async def get_asset(self, asset_id: UUID, version_limit: int) -> AssetCatalogRecord:
        asset = await self._session.scalar(
            select(BusinessObject).where(
                BusinessObject.workspace_id == self._workspace_id,
                BusinessObject.id == asset_id,
                BusinessObject.object_type == "asset",
            )
        )
        if asset is None:
            raise AssetCatalogNotFoundError("Asset was not found")
        versions = (
            await self._session.scalars(
                select(BusinessObjectVersion)
                .where(
                    BusinessObjectVersion.workspace_id == self._workspace_id,
                    BusinessObjectVersion.object_id == asset_id,
                )
                .order_by(BusinessObjectVersion.version.desc())
                .limit(version_limit)
            )
        ).all()
        files = await self._original_files([version.id for version in versions])
        return self._catalog_record(
            asset,
            tuple(self._version_record(asset, version, files) for version in versions),
        )

    async def _original_files(
        self, version_ids: list[UUID]
    ) -> dict[UUID, AssetFileRecord]:
        if not version_ids:
            return {}
        rows = (
            await self._session.execute(
                select(AssetVersionFile, AssetBlob)
                .join(
                    AssetBlob,
                    and_(
                        AssetBlob.workspace_id == AssetVersionFile.workspace_id,
                        AssetBlob.id == AssetVersionFile.blob_id,
                    ),
                )
                .where(
                    AssetVersionFile.workspace_id == self._workspace_id,
                    AssetVersionFile.business_object_version_id.in_(version_ids),
                    AssetVersionFile.role == "original",
                    AssetVersionFile.variant_key == "default",
                )
            )
        ).all()
        return {
            binding.business_object_version_id: AssetFileRecord(
                blob_id=blob.id,
                filename="",
                content_type=blob.detected_mime_type,
                byte_size=blob.byte_size,
                sha256=blob.sha256,
                scan_status=blob.scan_status,
                storage_status=blob.storage_status,
            )
            for binding, blob in rows
        }

    @staticmethod
    def _catalog_record(
        asset: BusinessObject, versions: tuple[AssetVersionRecord, ...]
    ) -> AssetCatalogRecord:
        return AssetCatalogRecord(
            id=asset.id,
            slug=asset.slug,
            name=asset.name,
            status=asset.status,
            current_version=asset.current_version,
            updated_at=asset.updated_at,
            versions=versions,
        )

    @staticmethod
    def _version_record(
        asset: BusinessObject,
        version: BusinessObjectVersion,
        files: dict[UUID, AssetFileRecord],
    ) -> AssetVersionRecord:
        file = files.get(version.id)
        if file is not None:
            file = AssetFileRecord(
                blob_id=file.blob_id,
                filename=str(version.payload.get("originalFilename", version.name)),
                content_type=file.content_type,
                byte_size=file.byte_size,
                sha256=file.sha256,
                scan_status=file.scan_status,
                storage_status=file.storage_status,
            )
        return AssetVersionRecord(
            id=version.id,
            version=version.version,
            name=version.name,
            status=version.status,
            locale=version.locale,
            payload=version.payload,
            change_summary=version.change_summary,
            created_at=version.created_at,
            original_file=file,
            downloadable=(
                asset.status == "active"
                and version.status == "active"
                and file is not None
                and file.scan_status == "clean"
                and file.storage_status == "available"
            ),
        )
