from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from temporalio import activity
from temporalio.exceptions import ApplicationError

from grovello.asset_uploads import AssetVerificationInput
from grovello.config import get_settings
from grovello.database import workspace_session
from grovello.models import AssetUploadSession, AuditEvent, OutboxEvent
from grovello.object_storage import StorageObjectRef
from grovello.s3_object_storage import ObjectStorageOperationError
from grovello.storage_factory import build_object_storage


@activity.defn(name="grovello-verify-asset-upload")
async def verify_asset_upload(payload: AssetVerificationInput) -> str:
    workspace_id = UUID(payload.workspace_id)
    upload_id = UUID(payload.upload_session_id)
    storage = build_object_storage(get_settings())
    if storage is None:
        raise ApplicationError("Object storage is not configured", non_retryable=True)

    if not await _move_to_verifying(workspace_id, upload_id):
        return "cancelled"
    location = StorageObjectRef(workspace_id, payload.object_key)
    try:
        stored = await storage.head_object(location)
        actual_sha256 = await storage.calculate_sha256(location)
    except ObjectStorageOperationError as error:
        if not error.retryable:
            await _fail(workspace_id, upload_id, error.code, str(error))
        raise ApplicationError(str(error), non_retryable=not error.retryable) from error

    mismatch = verification_failure(
        payload,
        stored.byte_size,
        stored.content_type,
        stored.checksum_sha256,
        actual_sha256,
    )
    if mismatch:
        await _fail(workspace_id, upload_id, mismatch, "Uploaded object failed integrity validation")
        raise ApplicationError(mismatch, non_retryable=True)

    async with workspace_session(workspace_id) as session:
        item = await session.scalar(
            select(AssetUploadSession).where(AssetUploadSession.id == upload_id).with_for_update()
        )
        if item is None or item.state == "cancelled":
            return "cancelled"
        if item.state == "scanning":
            return "scan_pending"
        item.state = "scanning"
        item.verified_size = stored.byte_size
        item.verified_mime_type = stored.content_type
        item.verified_sha256 = actual_sha256
        item.verified_at = datetime.now(UTC)
        item.verified_provider_version_id = stored.provider_version_id
        item.verified_etag = stored.etag
        item.scan_status = "pending"
        session.add(
            AuditEvent(
                id=uuid4(), workspace_id=workspace_id, actor_type="system", actor_id="asset-verifier",
                action="asset.upload.verified", resource_type="asset_upload_session",
                resource_id=str(upload_id), outcome="succeeded",
                evidence={"state": "scanning", "scanStatus": "pending"},
            )
        )
        session.add(
            OutboxEvent(
                id=uuid4(), workspace_id=workspace_id, aggregate_type="asset_upload_session",
                aggregate_id=str(upload_id), event_type="AssetUploadVerified", event_version=1,
                payload={"state": "scanning", "scanStatus": "pending"},
            )
        )
    return "scan_pending"


def verification_failure(
    payload: AssetVerificationInput,
    actual_size: int,
    actual_content_type: str,
    metadata_sha256: str,
    actual_sha256: str,
) -> str | None:
    if actual_size != payload.expected_content_length:
        return "content_length_mismatch"
    if actual_content_type != payload.expected_content_type:
        return "content_type_mismatch"
    if metadata_sha256 != payload.expected_sha256:
        return "declared_checksum_metadata_mismatch"
    if actual_sha256 != payload.expected_sha256:
        return "content_checksum_mismatch"
    return None


async def _move_to_verifying(workspace_id: UUID, upload_id: UUID) -> bool:
    async with workspace_session(workspace_id) as session:
        item = await session.scalar(
            select(AssetUploadSession).where(AssetUploadSession.id == upload_id).with_for_update()
        )
        if item is None:
            raise ApplicationError("Upload session was not found", non_retryable=True)
        if item.state == "cancelled":
            return False
        if item.state in {"verifying", "scanning"}:
            return True
        if item.state != "uploaded":
            raise ApplicationError(f"Invalid upload state: {item.state}", non_retryable=True)
        item.state = "verifying"
    return True


async def _fail(workspace_id: UUID, upload_id: UUID, code: str, detail: str) -> None:
    async with workspace_session(workspace_id) as session:
        item = await session.scalar(
            select(AssetUploadSession).where(AssetUploadSession.id == upload_id).with_for_update()
        )
        if item is None or item.state == "cancelled":
            return
        item.state = "failed"
        item.failure_code = code[:100]
        item.failure_detail = detail
        session.add(
            AuditEvent(
                id=uuid4(), workspace_id=workspace_id, actor_type="system", actor_id="asset-verifier",
                action="asset.upload.verification_failed", resource_type="asset_upload_session",
                resource_id=str(upload_id), outcome="failed", reason=detail,
                evidence={"failureCode": code},
            )
        )
