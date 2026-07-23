from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status

from grovello.access import ActorContext, AuthorizedWorkspace, access_directory
from grovello.asset_catalog import AssetCatalogStore, SqlAlchemyAssetCatalogStore
from grovello.asset_downloads import SqlAlchemyAssetDownloadStore
from grovello.asset_finalization import (
    AssetFinalizationLauncher,
    SqlAlchemyAssetFinalizationStore,
)
from grovello.asset_scanner import AssetScanner
from grovello.asset_uploads import AssetUploadStore, AssetVerificationLauncher, SqlAlchemyAssetUploadStore
from grovello.business_imports import (
    BusinessImportStore,
    ImportSourceVerificationLauncher,
    ImportValidationLauncher,
    SqlAlchemyBusinessImportStore,
)
from grovello.business_truth import BusinessTruthStore, SqlAlchemyBusinessTruthStore
from grovello.config import get_settings
from grovello.database import workspace_session
from grovello.import_change_sets import ImportApplyLauncher, SqlAlchemyImportChangeSetStore
from grovello.knowledge import KnowledgeStore, SqlAlchemyKnowledgeStore
from grovello.object_storage import ObjectStorage
from grovello.scanner_factory import build_asset_scanner
from grovello.storage_factory import build_object_storage
from grovello.temporal_asset_finalization import TemporalAssetFinalizationLauncher
from grovello.temporal_asset_verification import TemporalAssetVerificationLauncher
from grovello.temporal_import_apply import TemporalImportApplyLauncher
from grovello.temporal_import_source import TemporalImportSourceVerificationLauncher
from grovello.temporal_import_validation import TemporalImportValidationLauncher
from grovello.workspace_onboarding import (
    SqlAlchemyWorkspaceOnboardingStore,
    WorkspaceOnboardingStore,
)


async def require_actor(
    x_grovello_dev_subject: Annotated[str | None, Header()] = None,
    x_grovello_dev_session: Annotated[str | None, Header()] = None,
) -> ActorContext:
    settings = get_settings()
    if settings.environment == "production":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC session verification is not configured",
        )
    if not x_grovello_dev_subject or not x_grovello_dev_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Development session is required",
            headers={"WWW-Authenticate": "GrovelloDevelopmentSession"},
        )
    return ActorContext(subject_id=x_grovello_dev_subject, session_id=x_grovello_dev_session)


async def require_workspace_id(x_workspace_id: Annotated[str | None, Header()] = None) -> UUID:
    if not x_workspace_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="X-Workspace-ID is required")
    try:
        return UUID(x_workspace_id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Workspace-ID must be a UUID",
        ) from error


async def require_workspace_access(
    actor: Annotated[ActorContext, Depends(require_actor)],
    workspace_id: Annotated[UUID, Depends(require_workspace_id)],
) -> AuthorizedWorkspace:
    return access_directory.authorize(actor, workspace_id)


async def require_idempotency_key(
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str:
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key is required",
        )
    if len(idempotency_key) > 180:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key must be at most 180 characters",
        )
    return idempotency_key


async def get_business_truth_store(
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
) -> AsyncIterator[BusinessTruthStore]:
    async with workspace_session(access.workspace.id) as session:
        yield SqlAlchemyBusinessTruthStore(session, access.workspace.id)


async def get_knowledge_store(
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
) -> AsyncIterator[KnowledgeStore]:
    async with workspace_session(access.workspace.id) as session:
        yield SqlAlchemyKnowledgeStore(session, access.workspace.id)


async def get_workspace_onboarding_store(
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
) -> AsyncIterator[WorkspaceOnboardingStore]:
    async with workspace_session(access.workspace.id) as session:
        yield SqlAlchemyWorkspaceOnboardingStore(session, access.workspace.id)


@lru_cache
def get_object_storage() -> ObjectStorage | None:
    return build_object_storage(get_settings())


@lru_cache
def get_asset_scanner() -> AssetScanner | None:
    return build_asset_scanner(get_settings())


@lru_cache
def get_asset_verification_launcher() -> AssetVerificationLauncher:
    settings = get_settings()
    return TemporalAssetVerificationLauncher(
        settings.temporal_address,
        settings.temporal_namespace,
        settings.temporal_task_queue,
    )


@lru_cache
def get_asset_finalization_launcher() -> AssetFinalizationLauncher:
    settings = get_settings()
    return TemporalAssetFinalizationLauncher(
        settings.temporal_address,
        settings.temporal_namespace,
        settings.temporal_task_queue,
    )


@lru_cache
def get_import_source_verification_launcher() -> ImportSourceVerificationLauncher:
    settings = get_settings()
    return TemporalImportSourceVerificationLauncher(
        settings.temporal_address,
        settings.temporal_namespace,
        settings.temporal_task_queue,
    )


@lru_cache
def get_import_validation_launcher() -> ImportValidationLauncher:
    settings = get_settings()
    return TemporalImportValidationLauncher(
        settings.temporal_address,
        settings.temporal_namespace,
        settings.temporal_task_queue,
    )


@lru_cache
def get_import_apply_launcher() -> ImportApplyLauncher:
    settings = get_settings()
    return TemporalImportApplyLauncher(
        settings.temporal_address,
        settings.temporal_namespace,
        settings.temporal_task_queue,
    )


async def get_asset_upload_store(
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    storage: Annotated[ObjectStorage | None, Depends(get_object_storage)],
) -> AsyncIterator[AssetUploadStore]:
    if storage is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Object storage is not configured",
        )
    settings = get_settings()
    async with workspace_session(access.workspace.id) as session:
        yield SqlAlchemyAssetUploadStore(
            session,
            access.workspace.id,
            storage,
            max_upload_bytes=settings.asset_max_upload_bytes,
            upload_ttl_seconds=settings.asset_upload_ttl_seconds,
        )


async def get_business_import_store(
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    storage: Annotated[ObjectStorage | None, Depends(get_object_storage)],
) -> AsyncIterator[BusinessImportStore]:
    if storage is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Object storage is not configured",
        )
    settings = get_settings()
    async with workspace_session(access.workspace.id) as session:
        yield SqlAlchemyBusinessImportStore(
            session,
            access.workspace.id,
            storage,
            max_source_bytes=settings.import_max_source_bytes,
            upload_ttl_seconds=settings.import_upload_ttl_seconds,
            max_rows=settings.import_max_rows,
            max_columns=settings.import_max_columns,
            max_scalar_bytes=settings.import_max_scalar_bytes,
            max_json_depth=settings.import_max_json_depth,
            max_preview_rows=settings.import_preview_rows,
        )


async def get_import_change_set_store(
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
) -> AsyncIterator[SqlAlchemyImportChangeSetStore]:
    async with workspace_session(access.workspace.id) as session:
        yield SqlAlchemyImportChangeSetStore(session, access.workspace.id)


async def get_asset_catalog_store(
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
) -> AsyncIterator[AssetCatalogStore]:
    async with workspace_session(access.workspace.id) as session:
        yield SqlAlchemyAssetCatalogStore(session, access.workspace.id)


async def get_asset_finalization_store(
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
) -> AsyncIterator[SqlAlchemyAssetFinalizationStore]:
    async with workspace_session(access.workspace.id) as session:
        yield SqlAlchemyAssetFinalizationStore(session, access.workspace.id)


async def get_asset_download_store(
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    storage: Annotated[ObjectStorage | None, Depends(get_object_storage)],
) -> AsyncIterator[SqlAlchemyAssetDownloadStore]:
    if storage is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Object storage is not configured",
        )
    settings = get_settings()
    async with workspace_session(access.workspace.id) as session:
        yield SqlAlchemyAssetDownloadStore(
            session,
            access.workspace.id,
            storage,
            settings.asset_download_ttl_seconds,
        )
