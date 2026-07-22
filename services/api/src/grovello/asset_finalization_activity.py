from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from temporalio import activity
from temporalio.exceptions import ApplicationError

from grovello.asset_finalization import AssetFinalizationInput
from grovello.config import get_settings
from grovello.database import workspace_session
from grovello.models import (
    AssetBlob,
    AssetUploadSession,
    AssetVersionFile,
    AuditEvent,
    BusinessObject,
    BusinessObjectVersion,
    OutboxEvent,
)
from grovello.object_storage import CopyObjectRequest, DeleteObjectRequest, StorageObjectRef
from grovello.s3_object_storage import ObjectStorageIntegrityError, ObjectStorageOperationError
from grovello.storage_factory import build_object_storage


@dataclass(frozen=True, slots=True)
class PromotedAsset:
    object_key: str
    provider_version_id: str | None
    etag: str | None
    byte_size: int
    content_type: str
    sha256: str


@activity.defn(name="grovello-promote-asset-upload")
async def promote_asset_upload(payload: AssetFinalizationInput) -> PromotedAsset:
    workspace_id = UUID(payload.workspace_id)
    storage = build_object_storage(get_settings())
    if storage is None:
        raise ApplicationError("Object storage is not configured", non_retryable=True)
    source = StorageObjectRef(workspace_id, payload.object_key)
    destination = StorageObjectRef(workspace_id, payload.destination_object_key)
    try:
        try:
            stored = await storage.head_object(destination)
            _verify_promoted(payload, stored.byte_size, stored.content_type, stored.checksum_sha256)
        except ObjectStorageOperationError as error:
            if error.code not in {"404", "NoSuchKey", "NotFound"}:
                raise
            stored = await storage.copy_object(
                CopyObjectRequest(
                    source=source,
                    destination=destination,
                    expected_sha256=payload.expected_sha256,
                    expected_provider_version_id=payload.expected_provider_version_id,
                )
            )
            _verify_promoted(payload, stored.byte_size, stored.content_type, stored.checksum_sha256)
    except ObjectStorageOperationError as error:
        raise ApplicationError(str(error), non_retryable=not error.retryable) from error
    return PromotedAsset(
        object_key=stored.location.object_key,
        provider_version_id=stored.provider_version_id,
        etag=stored.etag,
        byte_size=stored.byte_size,
        content_type=stored.content_type,
        sha256=stored.checksum_sha256,
    )


@activity.defn(name="grovello-commit-asset-finalization")
async def commit_asset_finalization(args: tuple[AssetFinalizationInput, PromotedAsset]) -> str:
    payload, promoted = args
    workspace_id = UUID(payload.workspace_id)
    upload_id = UUID(payload.upload_session_id)
    asset_id = UUID(payload.asset_id)
    asset_version_id = UUID(payload.asset_version_id)
    blob_id = UUID(payload.blob_id)
    try:
        _verify_promoted(payload, promoted.byte_size, promoted.content_type, promoted.sha256)
    except ObjectStorageIntegrityError as error:
        raise ApplicationError(str(error), non_retryable=True) from error

    async with workspace_session(workspace_id) as session:
        item = await session.scalar(
            select(AssetUploadSession).where(AssetUploadSession.id == upload_id).with_for_update()
        )
        if item is None:
            raise ApplicationError("Upload session was not found", non_retryable=True)
        if item.state == "finalized":
            if (
                item.finalized_blob_id == blob_id
                and item.finalized_asset_id == asset_id
                and item.finalized_asset_version_id == asset_version_id
            ):
                return "finalized"
            raise ApplicationError("Finalization identifiers do not match", non_retryable=True)
        if (
            item.state != "finalizing"
            or item.scan_status != "clean"
            or item.finalization_request_hash != payload.request_hash
        ):
            raise ApplicationError("Upload is not eligible for finalization", non_retryable=True)

        business_object = await session.scalar(
            select(BusinessObject).where(
                BusinessObject.workspace_id == workspace_id,
                BusinessObject.id == asset_id,
            ).with_for_update()
        )
        if item.target_asset_id is None:
            if business_object is not None:
                raise ApplicationError("Asset identifier already exists", non_retryable=True)
            if payload.slug is None:
                raise ApplicationError("Asset slug is missing", non_retryable=True)
            slug_collision = await session.scalar(
                select(BusinessObject.id).where(
                    BusinessObject.workspace_id == workspace_id,
                    BusinessObject.object_type == "asset",
                    BusinessObject.slug == payload.slug,
                )
            )
            if slug_collision is not None:
                raise ApplicationError("Asset slug already exists", non_retryable=True)
            business_object = BusinessObject(
                id=asset_id, workspace_id=workspace_id, object_type="asset", slug=payload.slug,
                name=payload.name, status=payload.status, current_version=1,
            )
            session.add(business_object)
            version_number = 1
        else:
            if business_object is None or business_object.object_type != "asset":
                raise ApplicationError("Target asset was not found", non_retryable=True)
            version_number = business_object.current_version + 1
            business_object.current_version = version_number
            business_object.name = payload.name
            business_object.status = payload.status

        await _flush_finalization(session)

        blob = AssetBlob(
            id=blob_id,
            workspace_id=workspace_id,
            storage_profile="default",
            object_key=promoted.object_key,
            provider_version_id=promoted.provider_version_id,
            etag=promoted.etag,
            sha256=promoted.sha256,
            byte_size=promoted.byte_size,
            detected_mime_type=promoted.content_type,
            scan_status="clean",
            scan_provider=item.scan_provider,
            scan_reference=item.scan_reference,
            storage_status="available",
            encryption_mode=get_settings().object_storage_sse_mode,
        )
        version_payload = {
            **payload.metadata,
            "originalFilename": item.original_filename,
            "mediaType": promoted.content_type,
            "byteSize": promoted.byte_size,
            "sha256": promoted.sha256,
            "scanStatus": "clean",
            "scanProvider": item.scan_provider,
            "uploadSessionId": str(item.id),
        }
        version = BusinessObjectVersion(
            id=asset_version_id,
            workspace_id=workspace_id,
            object_id=asset_id,
            version=version_number,
            schema_version=1,
            name=payload.name,
            status=payload.status,
            locale=payload.locale,
            payload=version_payload,
            business_purpose=payload.business_purpose,
            actor_id=payload.actor_id,
            idempotency_key=f"asset-finalize-{upload_id}",
            source_type="owner_edit",
            source_ref=f"asset-upload-session:{upload_id}",
            change_summary=payload.change_summary,
            input_versions={"uploadSessionId": str(upload_id), "scanAttempts": item.scan_attempts},
        )
        binding = AssetVersionFile(
            id=uuid4(), workspace_id=workspace_id,
            business_object_version_id=asset_version_id, blob_id=blob_id,
            role="original", variant_key="default",
        )
        session.add_all([blob, version])
        await _flush_finalization(session)
        session.add(binding)
        await _flush_finalization(session)
        item.state = "finalized"
        item.finalized_blob_id = blob_id
        item.finalized_asset_id = asset_id
        item.finalized_asset_version_id = asset_version_id
        item.finalized_at = datetime.now(UTC)
        item.staging_cleanup_status = "pending"
        evidence = {
            "assetId": str(asset_id),
            "assetVersionId": str(asset_version_id),
            "blobId": str(blob_id),
            "status": payload.status,
            "scanStatus": "clean",
            "stagingCleanupStatus": "pending",
        }
        session.add(
            AuditEvent(
                id=uuid4(), workspace_id=workspace_id, actor_type=payload.actor_type,
                actor_id=payload.actor_id, session_id=payload.session_id, request_id=payload.request_id,
                action="asset.upload.finalized", resource_type="asset", resource_id=str(asset_id),
                outcome="succeeded", reason=payload.business_purpose, evidence=evidence,
            )
        )
        session.add(
            OutboxEvent(
                id=uuid4(), workspace_id=workspace_id, aggregate_type="Asset",
                aggregate_id=str(asset_id), event_type="AssetVersionFinalized", event_version=1,
                payload=evidence,
            )
        )
    return "finalized"


@activity.defn(name="grovello-cleanup-finalized-asset-staging")
async def cleanup_finalized_asset_staging(payload: AssetFinalizationInput) -> str:
    workspace_id = UUID(payload.workspace_id)
    upload_id = UUID(payload.upload_session_id)
    storage = build_object_storage(get_settings())
    if storage is None:
        raise ApplicationError("Object storage is not configured", non_retryable=True)
    try:
        await storage.delete_object(
            DeleteObjectRequest(
                target=StorageObjectRef(workspace_id, payload.object_key),
                expected_provider_version_id=payload.expected_provider_version_id,
            )
        )
    except ObjectStorageOperationError as error:
        raise ApplicationError(str(error), non_retryable=not error.retryable) from error
    async with workspace_session(workspace_id) as session:
        item = await session.scalar(
            select(AssetUploadSession).where(AssetUploadSession.id == upload_id).with_for_update()
        )
        if item is None or item.state != "finalized":
            raise ApplicationError("Finalized upload session was not found", non_retryable=True)
        if item.staging_cleanup_status != "complete":
            item.staging_cleanup_status = "complete"
            item.staging_cleanup_at = datetime.now(UTC)
            session.add(
                AuditEvent(
                    id=uuid4(), workspace_id=workspace_id, actor_type="system",
                    actor_id="asset-finalizer", action="asset.upload.staging_cleaned",
                    resource_type="asset_upload_session", resource_id=str(upload_id),
                    outcome="succeeded", evidence={"state": "finalized"},
                )
            )
    return "finalized"


@activity.defn(name="grovello-compensate-asset-promotion")
async def compensate_asset_promotion(args: tuple[AssetFinalizationInput, PromotedAsset]) -> str:
    payload, promoted = args
    workspace_id = UUID(payload.workspace_id)
    upload_id = UUID(payload.upload_session_id)
    storage = build_object_storage(get_settings())
    if storage is None:
        raise ApplicationError("Object storage is not configured", non_retryable=True)
    async with workspace_session(workspace_id) as session:
        item = await session.scalar(
            select(AssetUploadSession).where(AssetUploadSession.id == upload_id).with_for_update()
        )
        if item is None:
            raise ApplicationError("Upload session was not found", non_retryable=True)
        if item.state == "finalized":
            return "finalized"
        try:
            await storage.delete_object(
                DeleteObjectRequest(
                    target=StorageObjectRef(workspace_id, promoted.object_key),
                    expected_provider_version_id=promoted.provider_version_id,
                )
            )
        except ObjectStorageOperationError as error:
            raise ApplicationError(str(error), non_retryable=not error.retryable) from error
        _mark_failed(item, "asset_finalization_commit_failed")
        _append_failure(session, item)
    return "failed"


@activity.defn(name="grovello-fail-asset-finalization")
async def fail_asset_finalization(payload: AssetFinalizationInput) -> str:
    workspace_id = UUID(payload.workspace_id)
    upload_id = UUID(payload.upload_session_id)
    async with workspace_session(workspace_id) as session:
        item = await session.scalar(
            select(AssetUploadSession).where(AssetUploadSession.id == upload_id).with_for_update()
        )
        if item is None:
            raise ApplicationError("Upload session was not found", non_retryable=True)
        if item.state == "finalized":
            return "finalized"
        _mark_failed(item, "asset_finalization_promotion_failed")
        _append_failure(session, item)
    return "failed"


@activity.defn(name="grovello-mark-asset-staging-cleanup-failed")
async def mark_asset_staging_cleanup_failed(payload: AssetFinalizationInput) -> str:
    workspace_id = UUID(payload.workspace_id)
    upload_id = UUID(payload.upload_session_id)
    async with workspace_session(workspace_id) as session:
        item = await session.scalar(
            select(AssetUploadSession).where(AssetUploadSession.id == upload_id).with_for_update()
        )
        if item is None or item.state != "finalized":
            raise ApplicationError("Finalized upload session was not found", non_retryable=True)
        item.staging_cleanup_status = "failed"
        session.add(
            AuditEvent(
                id=uuid4(), workspace_id=workspace_id, actor_type="system",
                actor_id="asset-finalizer", action="asset.upload.staging_cleanup_failed",
                resource_type="asset_upload_session", resource_id=str(upload_id), outcome="failed",
                reason="Exact staging-version deletion exhausted retries",
                evidence={"state": "finalized", "stagingCleanupStatus": "failed"},
            )
        )
    return "finalized_cleanup_failed"


def _verify_promoted(
    payload: AssetFinalizationInput, byte_size: int, content_type: str, sha256: str
) -> None:
    if (
        byte_size != payload.expected_content_length
        or content_type != payload.expected_content_type
        or sha256 != payload.expected_sha256
    ):
        raise ObjectStorageIntegrityError("asset_finalization", "promoted_object_mismatch")


async def _flush_finalization(session) -> None:
    try:
        await session.flush()
    except IntegrityError as error:
        raise ApplicationError(
            "Asset finalization violates database constraints",
            non_retryable=True,
        ) from error


def _mark_failed(item: AssetUploadSession, code: str) -> None:
    item.state = "failed"
    item.failure_code = code
    item.failure_detail = "Asset finalization failed closed"
    item.staging_cleanup_status = "not_started"


def _append_failure(session, item: AssetUploadSession) -> None:
    session.add(
        AuditEvent(
            id=uuid4(), workspace_id=item.workspace_id, actor_type="system",
            actor_id="asset-finalizer", action="asset.upload.finalization_failed",
            resource_type="asset_upload_session", resource_id=str(item.id), outcome="failed",
            reason=item.failure_detail, evidence={"failureCode": item.failure_code},
        )
    )
    session.add(
        OutboxEvent(
            id=uuid4(), workspace_id=item.workspace_id,
            aggregate_type="asset_upload_session", aggregate_id=str(item.id),
            event_type="AssetFinalizationFailed", event_version=1,
            payload={"failureCode": item.failure_code},
        )
    )
