from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from temporalio import activity
from temporalio.exceptions import ApplicationError

from grovello.asset_scanner import AssetScannerError
from grovello.asset_uploads import AssetVerificationInput
from grovello.config import get_settings
from grovello.database import workspace_session
from grovello.models import AssetUploadSession, AuditEvent, OutboxEvent
from grovello.object_storage import CopyObjectRequest, DeleteObjectRequest, StorageObjectRef
from grovello.s3_object_storage import ObjectStorageIntegrityError, ObjectStorageOperationError
from grovello.scanner_factory import build_asset_scanner
from grovello.storage_factory import build_object_storage


@activity.defn(name="grovello-scan-asset-upload")
async def scan_asset_upload(payload: AssetVerificationInput) -> str:
    workspace_id = UUID(payload.workspace_id)
    upload_id = UUID(payload.upload_session_id)
    settings = get_settings()
    storage = build_object_storage(settings)
    scanner = build_asset_scanner(settings)
    if storage is None or scanner is None:
        raise ApplicationError("Asset scanning is not configured", non_retryable=True)

    terminal = await _start_attempt(workspace_id, upload_id)
    if terminal is not None:
        if terminal == "quarantined":
            await storage.delete_object(
                DeleteObjectRequest(
                    target=StorageObjectRef(workspace_id, payload.object_key),
                    expected_provider_version_id=await _verified_version(workspace_id, upload_id),
                )
            )
        return terminal
    source = StorageObjectRef(workspace_id, payload.object_key)
    try:
        result = await scanner.scan(_heartbeat_chunks(storage.iter_object_chunks(source)))
    except AssetScannerError as error:
        if not error.retryable:
            await _fail_scan(workspace_id, upload_id, error.code)
        raise ApplicationError(str(error), non_retryable=not error.retryable) from error
    except ObjectStorageOperationError as error:
        if not error.retryable:
            await _fail_scan(workspace_id, upload_id, error.code)
        raise ApplicationError(str(error), non_retryable=not error.retryable) from error

    if result.status == "clean":
        return await _record_clean(workspace_id, upload_id, result.provider)
    try:
        quarantine = StorageObjectRef(
            workspace_id,
            f"workspaces/{workspace_id}/quarantine/{upload_id}/{payload.expected_sha256}",
        )
        try:
            copied = await storage.head_object(quarantine)
            if copied.checksum_sha256 != payload.expected_sha256:
                raise ObjectStorageIntegrityError("quarantine", "quarantine_checksum_mismatch")
        except ObjectStorageOperationError as error:
            if error.code not in {"404", "NoSuchKey", "NotFound"}:
                raise
            copied = await storage.copy_object(
                CopyObjectRequest(
                    source=source,
                    destination=quarantine,
                    expected_sha256=payload.expected_sha256,
                    expected_provider_version_id=await _verified_version(workspace_id, upload_id),
                )
            )
        state = await _record_infected(
            workspace_id,
            upload_id,
            result.provider,
            result.reference,
            quarantine.object_key,
            copied.provider_version_id,
        )
        await storage.delete_object(
            DeleteObjectRequest(
                target=source,
                expected_provider_version_id=await _verified_version(workspace_id, upload_id),
            )
        )
        return state
    except ObjectStorageOperationError as error:
        raise ApplicationError(str(error), non_retryable=not error.retryable) from error


@activity.defn(name="grovello-fail-asset-scan")
async def fail_asset_scan(payload: AssetVerificationInput) -> str:
    return await _fail_scan(
        UUID(payload.workspace_id),
        UUID(payload.upload_session_id),
        "scanner_unavailable_after_retries",
    )


async def _start_attempt(workspace_id: UUID, upload_id: UUID) -> str | None:
    async with workspace_session(workspace_id) as session:
        item = await session.scalar(
            select(AssetUploadSession).where(AssetUploadSession.id == upload_id).with_for_update()
        )
        if item is None:
            raise ApplicationError("Upload session was not found", non_retryable=True)
        if item.state == "cancelled":
            return "cancelled"
        if item.state in {"ready_to_finalize", "quarantined", "failed"}:
            return item.state
        if item.state != "scanning":
            raise ApplicationError(f"Invalid scan state: {item.state}", non_retryable=True)
        item.scan_attempts += 1
    return None


async def _verified_version(workspace_id: UUID, upload_id: UUID) -> str | None:
    async with workspace_session(workspace_id) as session:
        item = await session.scalar(select(AssetUploadSession).where(AssetUploadSession.id == upload_id))
        return None if item is None else item.verified_provider_version_id


async def _record_clean(workspace_id: UUID, upload_id: UUID, provider: str) -> str:
    async with workspace_session(workspace_id) as session:
        item = await session.scalar(
            select(AssetUploadSession).where(AssetUploadSession.id == upload_id).with_for_update()
        )
        if item is None or item.state == "cancelled":
            return "cancelled"
        if item.state == "ready_to_finalize":
            return item.state
        item.state = "ready_to_finalize"
        item.scan_status = "clean"
        item.scan_provider = provider
        item.scanned_at = datetime.now(UTC)
        _append_result_events(session, item, "asset.upload.scan_clean", "AssetUploadScanClean", "succeeded")
    return "ready_to_finalize"


async def _record_infected(
    workspace_id: UUID,
    upload_id: UUID,
    provider: str,
    reference: str | None,
    quarantine_key: str,
    quarantine_version: str | None,
) -> str:
    async with workspace_session(workspace_id) as session:
        item = await session.scalar(
            select(AssetUploadSession).where(AssetUploadSession.id == upload_id).with_for_update()
        )
        if item is None:
            raise ApplicationError("Upload session was not found", non_retryable=True)
        item.state = "quarantined"
        item.scan_status = "infected"
        item.scan_provider = provider
        item.scan_reference = reference
        item.scanned_at = datetime.now(UTC)
        item.quarantine_object_key = quarantine_key
        item.quarantine_provider_version_id = quarantine_version
        item.quarantined_at = datetime.now(UTC)
        _append_result_events(
            session, item, "asset.upload.quarantined", "AssetUploadQuarantined", "blocked"
        )
    return "quarantined"


async def _fail_scan(workspace_id: UUID, upload_id: UUID, code: str) -> str:
    async with workspace_session(workspace_id) as session:
        item = await session.scalar(
            select(AssetUploadSession).where(AssetUploadSession.id == upload_id).with_for_update()
        )
        if item is None or item.state == "cancelled":
            return "cancelled"
        if item.state in {"ready_to_finalize", "quarantined"}:
            return item.state
        item.state = "failed"
        item.scan_status = "failed"
        item.failure_code = code[:100]
        item.failure_detail = "Asset scanner could not produce a trusted result"
        _append_result_events(session, item, "asset.upload.scan_failed", "AssetUploadScanFailed", "failed")
    return "failed"


def _append_result_events(
    session, item: AssetUploadSession, action: str, event_type: str, outcome: str
) -> None:
    evidence = {"state": item.state, "scanStatus": item.scan_status, "scanProvider": item.scan_provider}
    session.add(
        AuditEvent(
            id=uuid4(), workspace_id=item.workspace_id, actor_type="system", actor_id="asset-scanner",
            action=action, resource_type="asset_upload_session", resource_id=str(item.id),
            outcome=outcome, evidence=evidence,
        )
    )
    session.add(
        OutboxEvent(
            id=uuid4(), workspace_id=item.workspace_id, aggregate_type="asset_upload_session",
            aggregate_id=str(item.id), event_type=event_type, event_version=1, payload=evidence,
        )
    )


async def _heartbeat_chunks(chunks):
    streamed = 0
    async for chunk in chunks:
        streamed += len(chunk)
        activity.heartbeat({"streamedBytes": streamed})
        yield chunk
