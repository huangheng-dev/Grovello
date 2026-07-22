from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from grovello.access import AuthorizedWorkspace
from grovello.api.dependencies import (
    get_asset_catalog_store,
    get_asset_download_store,
    get_asset_finalization_launcher,
    get_asset_finalization_store,
    get_asset_upload_store,
    get_asset_verification_launcher,
    require_idempotency_key,
    require_workspace_access,
)
from grovello.asset_catalog import AssetCatalogNotFoundError, AssetCatalogRecord, AssetCatalogStore
from grovello.asset_downloads import (
    AssetDownloadDeniedError,
    AssetDownloadNotFoundError,
    SqlAlchemyAssetDownloadStore,
)
from grovello.asset_finalization import (
    AssetFinalizationLauncher,
    RequestAssetFinalizationCommand,
    SqlAlchemyAssetFinalizationStore,
)
from grovello.asset_uploads import (
    AssetUploadConflictError,
    AssetUploadNotFoundError,
    AssetUploadRecord,
    AssetUploadStore,
    AssetVerificationLauncher,
    CreateUploadCommand,
    UploadMutationContext,
)
from grovello.schemas import (
    ApiEnvelope,
    ApiMeta,
    AssetCatalogItemSummary,
    AssetCatalogSummary,
    AssetCatalogVersionSummary,
    AssetDownloadSummary,
    AssetFileSummary,
    AssetFinalizationRequest,
    AssetUploadCreateSummary,
    AssetUploadGrantSummary,
    AssetUploadMutationSummary,
    AssetUploadSessionCreate,
    AssetUploadSessionSummary,
)

router = APIRouter()


def _catalog_summary(item: AssetCatalogRecord) -> AssetCatalogItemSummary:
    return AssetCatalogItemSummary(
        id=item.id,
        slug=item.slug,
        name=item.name,
        status=item.status,
        current_version=item.current_version,
        updated_at=item.updated_at,
        versions=[
            AssetCatalogVersionSummary(
                id=version.id,
                version=version.version,
                name=version.name,
                status=version.status,
                locale=version.locale,
                payload=version.payload,
                change_summary=version.change_summary,
                created_at=version.created_at,
                original_file=(
                    AssetFileSummary(
                        blob_id=version.original_file.blob_id,
                        filename=version.original_file.filename,
                        content_type=version.original_file.content_type,
                        byte_size=version.original_file.byte_size,
                        sha256=version.original_file.sha256,
                        scan_status=version.original_file.scan_status,
                        storage_status=version.original_file.storage_status,
                    )
                    if version.original_file
                    else None
                ),
                downloadable=version.downloadable,
            )
            for version in item.versions
        ],
    )


@router.get("", response_model=ApiEnvelope[AssetCatalogSummary])
async def list_assets(
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[AssetCatalogStore, Depends(get_asset_catalog_store)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiEnvelope[AssetCatalogSummary]:
    access.require("asset.read")
    items = await store.list_assets(limit)
    return ApiEnvelope(
        data=AssetCatalogSummary(items=[_catalog_summary(item) for item in items]),
        meta=ApiMeta(request_id=request.state.request_id),
    )


@router.get("/{asset_id}", response_model=ApiEnvelope[AssetCatalogItemSummary])
async def get_asset(
    asset_id: UUID,
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[AssetCatalogStore, Depends(get_asset_catalog_store)],
    version_limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiEnvelope[AssetCatalogItemSummary]:
    access.require("asset.read")
    try:
        item = await store.get_asset(asset_id, version_limit)
    except AssetCatalogNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return ApiEnvelope(
        data=_catalog_summary(item),
        meta=ApiMeta(request_id=request.state.request_id),
    )


def _context(request: Request, access: AuthorizedWorkspace, key: str) -> UploadMutationContext:
    return UploadMutationContext(
        actor_type=access.actor.actor_type,
        actor_id=access.actor.subject_id,
        session_id=access.actor.session_id,
        request_id=request.state.request_id,
        idempotency_key=key,
    )


def _summary(item: AssetUploadRecord) -> AssetUploadSessionSummary:
    return AssetUploadSessionSummary(
        **item.__dict__ if hasattr(item, "__dict__") else {
            field: getattr(item, field) for field in item.__dataclass_fields__
        },
    )


def _raise(error: Exception) -> NoReturn:
    if isinstance(error, AssetUploadNotFoundError):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(error, AssetUploadConflictError):
        raise HTTPException(status_code=409, detail=str(error)) from error
    raise error


@router.post(
    "/upload-sessions",
    response_model=ApiEnvelope[AssetUploadCreateSummary],
    status_code=status.HTTP_201_CREATED,
)
async def create_upload_session(
    payload: AssetUploadSessionCreate,
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[AssetUploadStore, Depends(get_asset_upload_store)],
    key: Annotated[str, Depends(require_idempotency_key)],
) -> ApiEnvelope[AssetUploadCreateSummary]:
    access.require("asset.write")
    try:
        result = await store.create(
            CreateUploadCommand(
                original_filename=payload.original_filename,
                content_type=payload.content_type,
                content_length=payload.content_length,
                checksum_sha256=payload.checksum_sha256,
                business_purpose=payload.business_purpose,
                target_asset_id=payload.target_asset_id,
            ),
            _context(request, access, key),
        )
    except (AssetUploadNotFoundError, AssetUploadConflictError) as error:
        _raise(error)
    return ApiEnvelope(
        data=AssetUploadCreateSummary(
            session=_summary(result.session),
            upload=AssetUploadGrantSummary(
                method=result.grant.method.value,
                url=result.grant.url,
                fields=result.grant.fields,
                expires_at=result.grant.expires_at,
            ),
            idempotent_replay=result.idempotent_replay,
        ),
        meta=ApiMeta(request_id=request.state.request_id),
    )


@router.get(
    "/upload-sessions/{upload_session_id}",
    response_model=ApiEnvelope[AssetUploadSessionSummary],
)
async def get_upload_session(
    upload_session_id: UUID,
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[AssetUploadStore, Depends(get_asset_upload_store)],
) -> ApiEnvelope[AssetUploadSessionSummary]:
    access.require("asset.read")
    try:
        item = await store.get(upload_session_id)
    except AssetUploadNotFoundError as error:
        _raise(error)
    return ApiEnvelope(data=_summary(item), meta=ApiMeta(request_id=request.state.request_id))


@router.post(
    "/upload-sessions/{upload_session_id}/complete",
    response_model=ApiEnvelope[AssetUploadMutationSummary],
    status_code=status.HTTP_202_ACCEPTED,
)
async def complete_upload_session(
    upload_session_id: UUID,
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[AssetUploadStore, Depends(get_asset_upload_store)],
    launcher: Annotated[AssetVerificationLauncher, Depends(get_asset_verification_launcher)],
    key: Annotated[str, Depends(require_idempotency_key)],
) -> ApiEnvelope[AssetUploadMutationSummary]:
    access.require("asset.write")
    try:
        result, verification = await store.complete(upload_session_id, _context(request, access, key))
        await store.commit()
        assert result.session.workflow_id is not None
        await launcher.start(result.session.workflow_id, verification)
    except (AssetUploadNotFoundError, AssetUploadConflictError) as error:
        _raise(error)
    except Exception as error:
        raise HTTPException(status_code=503, detail="Verification workflow is unavailable") from error
    return ApiEnvelope(
        data=AssetUploadMutationSummary(
            session=_summary(result.session), idempotent_replay=result.idempotent_replay
        ),
        meta=ApiMeta(request_id=request.state.request_id),
    )


@router.post(
    "/upload-sessions/{upload_session_id}/cancel",
    response_model=ApiEnvelope[AssetUploadMutationSummary],
)
async def cancel_upload_session(
    upload_session_id: UUID,
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[AssetUploadStore, Depends(get_asset_upload_store)],
    launcher: Annotated[AssetVerificationLauncher, Depends(get_asset_verification_launcher)],
    key: Annotated[str, Depends(require_idempotency_key)],
) -> ApiEnvelope[AssetUploadMutationSummary]:
    access.require("asset.write")
    try:
        result = await store.cancel(upload_session_id, _context(request, access, key))
        await store.commit()
        if result.session.workflow_id:
            await launcher.cancel(result.session.workflow_id)
    except (AssetUploadNotFoundError, AssetUploadConflictError) as error:
        _raise(error)
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail="Verification workflow cancellation is pending",
        ) from error
    return ApiEnvelope(
        data=AssetUploadMutationSummary(
            session=_summary(result.session), idempotent_replay=result.idempotent_replay
        ),
        meta=ApiMeta(request_id=request.state.request_id),
    )


@router.post(
    "/upload-sessions/{upload_session_id}/finalize",
    response_model=ApiEnvelope[AssetUploadMutationSummary],
    status_code=status.HTTP_202_ACCEPTED,
)
async def finalize_upload_session(
    upload_session_id: UUID,
    payload: AssetFinalizationRequest,
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[SqlAlchemyAssetFinalizationStore, Depends(get_asset_finalization_store)],
    launcher: Annotated[AssetFinalizationLauncher, Depends(get_asset_finalization_launcher)],
    key: Annotated[str, Depends(require_idempotency_key)],
) -> ApiEnvelope[AssetUploadMutationSummary]:
    access.require("asset.write")
    if payload.status == "active":
        access.require("asset.approve")
    try:
        result = await store.request(
            upload_session_id,
            RequestAssetFinalizationCommand(
                name=payload.name,
                slug=payload.slug,
                locale=payload.locale,
                status=payload.status,
                metadata=payload.metadata,
                change_summary=payload.change_summary,
            ),
            _context(request, access, key),
        )
        await store.commit()
        await launcher.start(result.workflow_id, result.payload)
    except (AssetUploadNotFoundError, AssetUploadConflictError) as error:
        _raise(error)
    except Exception as error:
        raise HTTPException(status_code=503, detail="Finalization workflow is unavailable") from error
    return ApiEnvelope(
        data=AssetUploadMutationSummary(
            session=_summary(result.session), idempotent_replay=result.idempotent_replay
        ),
        meta=ApiMeta(request_id=request.state.request_id),
    )


@router.get(
    "/{asset_id}/versions/{asset_version_id}/download",
    response_model=ApiEnvelope[AssetDownloadSummary],
)
async def create_asset_download(
    asset_id: UUID,
    asset_version_id: UUID,
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[SqlAlchemyAssetDownloadStore, Depends(get_asset_download_store)],
) -> ApiEnvelope[AssetDownloadSummary]:
    access.require("asset.download")
    context = UploadMutationContext(
        actor_type=access.actor.actor_type,
        actor_id=access.actor.subject_id,
        session_id=access.actor.session_id,
        request_id=request.state.request_id,
        idempotency_key=f"download-{request.state.request_id}",
    )
    try:
        result = await store.authorize(asset_id, asset_version_id, context)
    except AssetDownloadNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except AssetDownloadDeniedError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return ApiEnvelope(
        data=AssetDownloadSummary(
            asset_id=result.asset_id,
            asset_version_id=result.asset_version_id,
            blob_id=result.blob_id,
            filename=result.filename,
            content_type=result.content_type,
            byte_size=result.byte_size,
            sha256=result.sha256,
            url=result.grant.url,
            expires_at=result.grant.expires_at,
            headers=result.grant.headers,
        ),
        meta=ApiMeta(request_id=request.state.request_id),
    )
