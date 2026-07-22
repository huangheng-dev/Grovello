from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from temporalio import activity
from temporalio.exceptions import ApplicationError

from grovello.asset_scanner import AssetScannerError
from grovello.asset_verification_activity import verification_failure
from grovello.business_imports import ImportSourceVerificationInput
from grovello.config import get_settings
from grovello.database import workspace_session
from grovello.models import AuditEvent, ImportJob, ImportSource, OutboxEvent
from grovello.object_storage import CopyObjectRequest, DeleteObjectRequest, StorageObjectRef
from grovello.s3_object_storage import ObjectStorageIntegrityError, ObjectStorageOperationError
from grovello.scanner_factory import build_asset_scanner
from grovello.storage_factory import build_object_storage


@activity.defn(name="grovello-verify-import-source")
async def verify_import_source(payload: ImportSourceVerificationInput) -> str:
    workspace_id = UUID(payload.workspace_id)
    job_id = UUID(payload.job_id)
    source_id = UUID(payload.source_id)
    storage = build_object_storage(get_settings())
    if storage is None:
        raise ApplicationError("Object storage is not configured", non_retryable=True)
    if not await _move_to_verifying(workspace_id, job_id, source_id):
        return "cancelled"

    location = StorageObjectRef(workspace_id, payload.object_key)
    try:
        stored = await storage.head_object(location)
        actual_sha256 = await storage.calculate_sha256(location)
    except ObjectStorageOperationError as error:
        if not error.retryable:
            await _fail(workspace_id, job_id, source_id, error.code, str(error))
        raise ApplicationError(str(error), non_retryable=not error.retryable) from error

    mismatch = verification_failure(
        payload,
        stored.byte_size,
        stored.content_type,
        stored.checksum_sha256,
        actual_sha256,
    )
    if mismatch:
        await _fail(
            workspace_id,
            job_id,
            source_id,
            mismatch,
            "Import source failed integrity validation",
        )
        raise ApplicationError(mismatch, non_retryable=True)

    async with workspace_session(workspace_id) as session:
        job, source = await _locked_records(session, job_id, source_id)
        if job.status == "cancelled" or source.state == "cancelled":
            return "cancelled"
        if job.status == "scanning" and source.state == "scanning":
            return "scan_pending"
        job.status = "scanning"
        source.state = "scanning"
        source.verified_size = stored.byte_size
        source.verified_mime_type = stored.content_type
        source.verified_sha256 = actual_sha256
        source.verified_at = datetime.now(UTC)
        source.provider_version_id = stored.provider_version_id
        source.etag = stored.etag
        source.scan_status = "pending"
        _append_result_events(
            session,
            job,
            "business_truth.import.source_verified",
            "BusinessImportSourceVerified",
            "succeeded",
        )
    return "scan_pending"


@activity.defn(name="grovello-scan-import-source")
async def scan_import_source(payload: ImportSourceVerificationInput) -> str:
    workspace_id = UUID(payload.workspace_id)
    job_id = UUID(payload.job_id)
    source_id = UUID(payload.source_id)
    settings = get_settings()
    storage = build_object_storage(settings)
    scanner = build_asset_scanner(settings)
    if storage is None or scanner is None:
        raise ApplicationError("Import source scanning is not configured", non_retryable=True)

    terminal, provider_version = await _start_scan_attempt(workspace_id, job_id, source_id)
    source_ref = StorageObjectRef(workspace_id, payload.object_key)
    if terminal is not None:
        return terminal
    try:
        result = await scanner.scan(_heartbeat_chunks(storage.iter_object_chunks(source_ref)))
    except AssetScannerError as error:
        if not error.retryable:
            await _fail_scan(workspace_id, job_id, source_id, error.code)
        raise ApplicationError(str(error), non_retryable=not error.retryable) from error
    except ObjectStorageOperationError as error:
        if not error.retryable:
            await _fail_scan(workspace_id, job_id, source_id, error.code)
        raise ApplicationError(str(error), non_retryable=not error.retryable) from error

    if result.status == "clean":
        return await _record_clean(workspace_id, job_id, source_id, result.provider)

    quarantine = StorageObjectRef(
        workspace_id,
        f"workspaces/{workspace_id}/quarantine/imports/{job_id}/{payload.expected_sha256}",
    )
    try:
        try:
            copied = await storage.head_object(quarantine)
            if copied.checksum_sha256 != payload.expected_sha256:
                raise ObjectStorageIntegrityError("quarantine", "quarantine_checksum_mismatch")
        except ObjectStorageOperationError as error:
            if error.code not in {"404", "NoSuchKey", "NotFound"}:
                raise
            copied = await storage.copy_object(
                CopyObjectRequest(
                    source=source_ref,
                    destination=quarantine,
                    expected_sha256=payload.expected_sha256,
                    expected_provider_version_id=provider_version,
                )
            )
        state = await _record_infected(
            workspace_id,
            job_id,
            source_id,
            result.provider,
            result.reference,
            quarantine.object_key,
            copied.provider_version_id,
        )
        await storage.delete_object(
            DeleteObjectRequest(
                target=source_ref,
                expected_provider_version_id=provider_version,
            )
        )
        return state
    except ObjectStorageOperationError as error:
        raise ApplicationError(str(error), non_retryable=not error.retryable) from error


@activity.defn(name="grovello-fail-import-source-scan")
async def fail_import_source_scan(payload: ImportSourceVerificationInput) -> str:
    return await _fail_scan(
        UUID(payload.workspace_id),
        UUID(payload.job_id),
        UUID(payload.source_id),
        "scanner_unavailable_after_retries",
    )


async def _move_to_verifying(workspace_id: UUID, job_id: UUID, source_id: UUID) -> bool:
    async with workspace_session(workspace_id) as session:
        job, source = await _locked_records(session, job_id, source_id)
        if job.status == "cancelled" or source.state == "cancelled":
            return False
        if job.status in {"verifying", "scanning"}:
            return True
        if job.status != "uploaded" or source.state != "uploaded":
            raise ApplicationError("Invalid import source verification state", non_retryable=True)
        job.status = "verifying"
        source.state = "verifying"
    return True


async def _start_scan_attempt(
    workspace_id: UUID, job_id: UUID, source_id: UUID
) -> tuple[str | None, str | None]:
    async with workspace_session(workspace_id) as session:
        job, source = await _locked_records(session, job_id, source_id)
        if job.status == "cancelled" or source.state == "cancelled":
            return "cancelled", source.provider_version_id
        if job.status == "ready_for_mapping" and source.state == "clean":
            return "ready_for_mapping", source.provider_version_id
        if job.status == "failed" or source.state in {"failed", "quarantined"}:
            return job.status, source.provider_version_id
        if job.status != "scanning" or source.state != "scanning":
            raise ApplicationError("Invalid import source scan state", non_retryable=True)
        source.scan_attempts += 1
        return None, source.provider_version_id


async def _record_clean(
    workspace_id: UUID, job_id: UUID, source_id: UUID, provider: str
) -> str:
    async with workspace_session(workspace_id) as session:
        job, source = await _locked_records(session, job_id, source_id)
        if job.status == "cancelled" or source.state == "cancelled":
            return "cancelled"
        job.status = "ready_for_mapping"
        source.state = "clean"
        source.scan_status = "clean"
        source.scan_provider = provider
        source.scanned_at = datetime.now(UTC)
        _append_result_events(
            session,
            job,
            "business_truth.import.source_scan_clean",
            "BusinessImportSourceScanClean",
            "succeeded",
        )
    return "ready_for_mapping"


async def _record_infected(
    workspace_id: UUID,
    job_id: UUID,
    source_id: UUID,
    provider: str,
    reference: str | None,
    quarantine_key: str,
    quarantine_version: str | None,
) -> str:
    async with workspace_session(workspace_id) as session:
        job, source = await _locked_records(session, job_id, source_id)
        job.status = "failed"
        job.failure_code = "infected_source"
        job.failure_detail = "Import source was quarantined by malware scanning"
        source.state = "quarantined"
        source.scan_status = "infected"
        source.scan_provider = provider
        source.scan_reference = reference
        source.scanned_at = datetime.now(UTC)
        source.quarantine_object_key = quarantine_key
        source.quarantine_provider_version_id = quarantine_version
        source.quarantined_at = datetime.now(UTC)
        _append_result_events(
            session,
            job,
            "business_truth.import.source_quarantined",
            "BusinessImportSourceQuarantined",
            "blocked",
        )
    return "quarantined"


async def _fail_scan(workspace_id: UUID, job_id: UUID, source_id: UUID, code: str) -> str:
    await _fail(
        workspace_id,
        job_id,
        source_id,
        code,
        "Import source scanner could not produce a trusted result",
        scan_failed=True,
    )
    return "failed"


async def _fail(
    workspace_id: UUID,
    job_id: UUID,
    source_id: UUID,
    code: str,
    detail: str,
    *,
    scan_failed: bool = False,
) -> None:
    async with workspace_session(workspace_id) as session:
        job, source = await _locked_records(session, job_id, source_id)
        if job.status == "cancelled" or source.state == "cancelled":
            return
        job.status = "failed"
        job.failure_code = code[:100]
        job.failure_detail = detail
        source.state = "failed"
        if scan_failed:
            source.scan_status = "failed"
        _append_result_events(
            session,
            job,
            "business_truth.import.source_failed",
            "BusinessImportSourceFailed",
            "failed",
        )


async def _locked_records(session, job_id: UUID, source_id: UUID):
    job = await session.scalar(select(ImportJob).where(ImportJob.id == job_id).with_for_update())
    source = await session.scalar(
        select(ImportSource).where(
            ImportSource.id == source_id, ImportSource.job_id == job_id
        ).with_for_update()
    )
    if job is None or source is None:
        raise ApplicationError("Import job or source was not found", non_retryable=True)
    return job, source


def _append_result_events(session, job: ImportJob, action: str, event_type: str, outcome: str) -> None:
    evidence = {"status": job.status, "failureCode": job.failure_code}
    session.add(
        AuditEvent(
            id=uuid4(), workspace_id=job.workspace_id,
            actor_type="system", actor_id="import-source-validator",
            action=action, resource_type="import_job", resource_id=str(job.id),
            outcome=outcome, reason=job.failure_detail, evidence=evidence,
        )
    )
    session.add(
        OutboxEvent(
            id=uuid4(), workspace_id=job.workspace_id,
            aggregate_type="import_job", aggregate_id=str(job.id),
            event_type=event_type, event_version=1, payload=evidence,
        )
    )


async def _heartbeat_chunks(chunks):
    streamed = 0
    async for chunk in chunks:
        streamed += len(chunk)
        activity.heartbeat({"streamedBytes": streamed})
        yield chunk
