import hashlib
from collections import Counter
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from temporalio import activity
from temporalio.exceptions import ApplicationError

from grovello.business_imports import ImportValidationInput
from grovello.config import get_settings
from grovello.database import workspace_session
from grovello.import_validation import (
    PARSER_VERSION,
    CanonicalObjectSnapshot,
    FieldMapping,
    ImportLimits,
    ImportValidationError,
    parse_source,
    validate_rows,
)
from grovello.models import (
    AuditEvent,
    BusinessObject,
    BusinessObjectVersion,
    ImportIssue,
    ImportJob,
    ImportMappingVersion,
    ImportRow,
    ImportSource,
    OutboxEvent,
)
from grovello.object_storage import StorageObjectRef
from grovello.s3_object_storage import ObjectStorageOperationError
from grovello.storage_factory import build_object_storage


@activity.defn(name="grovello-validate-import")
async def validate_import(payload: ImportValidationInput) -> str:
    workspace_id = UUID(payload.workspace_id)
    job_id = UUID(payload.job_id)
    mapping_id = UUID(payload.mapping_version_id)
    settings = get_settings()
    storage = build_object_storage(settings)
    if storage is None:
        raise ApplicationError("Object storage is not configured", non_retryable=True)

    job, source, mapping = await _load_execution(workspace_id, job_id, mapping_id)
    if job.status in {"cancelled", "ready_for_review"}:
        return job.status
    location = StorageObjectRef(workspace_id, source.object_key, source.storage_profile)
    try:
        content = await _read_bounded(storage.iter_object_chunks(location), settings.import_max_source_bytes)
    except ObjectStorageOperationError as error:
        raise ApplicationError(str(error), non_retryable=not error.retryable) from error
    if len(content) != source.verified_size or hashlib.sha256(content).hexdigest() != source.verified_sha256:
        await _record_source_failure(
            workspace_id,
            job_id,
            "source_changed_after_verification",
            "Verified import source changed before parsing",
        )
        return "failed"

    limits = ImportLimits(
        max_source_bytes=settings.import_max_source_bytes,
        max_rows=settings.import_max_rows,
        max_columns=settings.import_max_columns,
        max_scalar_bytes=settings.import_max_scalar_bytes,
        max_json_depth=settings.import_max_json_depth,
    )
    try:
        parsed = parse_source(
            content,
            source_format=job.source_format,
            delimiter=mapping.delimiter,
            limits=limits,
            object_type=job.object_type,
            locale=job.locale,
            schema_version=job.schema_version,
        )
        canonical, evidence_versions = await _canonical_snapshot(workspace_id)
        result = validate_rows(
            parsed,
            source_format=job.source_format,
            declared_source_fields=tuple(mapping.source_fields),
            mappings=_mapping_fields(mapping),
            object_type=job.object_type,
            locale=job.locale,
            limits=limits,
            canonical_objects=canonical,
            evidence_version_ids=evidence_versions,
        )
        if result.schema_fingerprint != mapping.schema_fingerprint:
            raise ImportValidationError(
                "source_schema_mismatch",
                "Verified source schema does not match the immutable mapping fingerprint",
            )
    except ImportValidationError as error:
        await _record_source_failure(workspace_id, job_id, error.code, str(error))
        return "failed"

    return await _persist_result(workspace_id, job_id, mapping_id, result)


@activity.defn(name="grovello-fail-import-validation")
async def fail_import_validation(payload: ImportValidationInput) -> str:
    await _record_source_failure(
        UUID(payload.workspace_id),
        UUID(payload.job_id),
        "validation_unavailable_after_retries",
        "Import validation could not complete after bounded retries",
    )
    return "failed"


async def _load_execution(
    workspace_id: UUID, job_id: UUID, mapping_id: UUID
) -> tuple[ImportJob, ImportSource, ImportMappingVersion]:
    async with workspace_session(workspace_id) as session:
        job = await session.scalar(select(ImportJob).where(ImportJob.id == job_id).with_for_update())
        source = await session.scalar(
            select(ImportSource).where(ImportSource.job_id == job_id).with_for_update()
        )
        mapping = await session.scalar(
            select(ImportMappingVersion).where(
                ImportMappingVersion.id == mapping_id,
                ImportMappingVersion.job_id == job_id,
            )
        )
        if job is None or source is None or mapping is None:
            raise ApplicationError("Import validation records were not found", non_retryable=True)
        if job.selected_mapping_version_id != mapping_id:
            raise ApplicationError("Import mapping is no longer selected", non_retryable=True)
        if job.status == "cancelled":
            return job, source, mapping
        if job.status == "ready_for_review" and job.parser_version == PARSER_VERSION:
            return job, source, mapping
        if job.status != "validating" or source.state != "clean" or source.scan_status != "clean":
            raise ApplicationError("Import validation state is invalid", non_retryable=True)
        return job, source, mapping


async def _read_bounded(chunks, maximum: int) -> bytes:
    content = bytearray()
    async for chunk in chunks:
        content.extend(chunk)
        if len(content) > maximum:
            raise ApplicationError("Import source exceeds configured byte limit", non_retryable=True)
        activity.heartbeat({"parsedBytes": len(content)})
    return bytes(content)


async def _canonical_snapshot(
    workspace_id: UUID,
) -> tuple[tuple[CanonicalObjectSnapshot, ...], frozenset[UUID]]:
    async with workspace_session(workspace_id) as session:
        pairs = (
            await session.execute(
                select(BusinessObject, BusinessObjectVersion)
                .join(
                    BusinessObjectVersion,
                    (BusinessObjectVersion.object_id == BusinessObject.id)
                    & (BusinessObjectVersion.version == BusinessObject.current_version),
                )
                .where(BusinessObject.workspace_id == workspace_id)
            )
        ).all()
        snapshots = tuple(
            CanonicalObjectSnapshot(
                object_id=item.id,
                object_type=item.object_type,
                slug=item.slug,
                current_version_id=version.id,
                payload=version.payload,
            )
            for item, version in pairs
        )
        evidence_versions = frozenset(
            (
                await session.scalars(
                    select(BusinessObjectVersion.id)
                    .join(BusinessObject, BusinessObject.id == BusinessObjectVersion.object_id)
                    .where(
                        BusinessObject.workspace_id == workspace_id,
                        BusinessObject.object_type == "evidence",
                    )
                )
            ).all()
        )
        return snapshots, evidence_versions


async def _persist_result(workspace_id: UUID, job_id: UUID, mapping_id: UUID, result) -> str:
    async with workspace_session(workspace_id) as session:
        job = await session.scalar(select(ImportJob).where(ImportJob.id == job_id).with_for_update())
        if job is None:
            raise ApplicationError("Import job was not found", non_retryable=True)
        if job.status == "cancelled":
            return "cancelled"
        if job.status == "ready_for_review" and job.parser_version == PARSER_VERSION:
            return "ready_for_review"
        if job.status != "validating" or job.selected_mapping_version_id != mapping_id:
            raise ApplicationError("Import validation state changed", non_retryable=True)

        await session.execute(
            delete(ImportIssue).where(
                ImportIssue.workspace_id == workspace_id,
                ImportIssue.job_id == job_id,
            )
        )
        await session.execute(
            delete(ImportRow).where(
                ImportRow.workspace_id == workspace_id,
                ImportRow.job_id == job_id,
            )
        )
        status_counts = Counter(row.status for row in result.rows)
        issue_counts: Counter[str] = Counter()
        for row in result.rows:
            staged = ImportRow(
                id=uuid4(),
                workspace_id=workspace_id,
                job_id=job_id,
                mapping_version_id=mapping_id,
                source_row_number=row.source_row_number,
                content_hash=row.content_hash,
                normalized_data=row.normalized_data,
                target_identity=row.target_identity,
                status=row.status,
            )
            session.add(staged)
            for issue in row.issues:
                issue_counts[issue.code] += 1
                session.add(
                    ImportIssue(
                        id=uuid4(),
                        workspace_id=workspace_id,
                        job_id=job_id,
                        row_id=staged.id,
                        code=issue.code,
                        severity=issue.severity,
                        field_locator=issue.field_locator,
                        message=issue.message,
                        redacted_sample=issue.redacted_sample,
                    )
                )
        job.status = "ready_for_review"
        job.total_rows = len(result.rows)
        job.valid_rows = result.valid_rows
        job.invalid_rows = result.invalid_rows
        job.parser_version = PARSER_VERSION
        job.failure_code = None
        job.failure_detail = None
        job.result_summary = {
            "parserVersion": PARSER_VERSION,
            "schemaFingerprint": result.schema_fingerprint,
            "statusCounts": dict(sorted(status_counts.items())),
            "issueCounts": dict(sorted(issue_counts.items())),
            "appliedRows": 0,
        }
        _append_events(
            session,
            job,
            "business_truth.import.validation_completed",
            "BusinessImportValidationCompleted",
            "succeeded",
        )
    return "ready_for_review"


async def _record_source_failure(workspace_id: UUID, job_id: UUID, code: str, detail: str) -> None:
    async with workspace_session(workspace_id) as session:
        job = await session.scalar(select(ImportJob).where(ImportJob.id == job_id).with_for_update())
        if job is None or job.status == "cancelled":
            return
        job.status = "failed"
        job.failure_code = code[:100]
        job.failure_detail = detail[:500]
        job.parser_version = PARSER_VERSION
        job.result_summary = {"parserVersion": PARSER_VERSION, "failureCode": job.failure_code}
        _append_events(
            session,
            job,
            "business_truth.import.validation_failed",
            "BusinessImportValidationFailed",
            "failed",
        )


def _mapping_fields(mapping: ImportMappingVersion) -> tuple[FieldMapping, ...]:
    return tuple(
        FieldMapping(
            source=field.get("source"),
            target=field["target"],
            transform=field.get("transform", "identity"),
            default_value=field.get("defaultValue"),
            has_default=field.get("hasDefault", False),
            separator=field.get("separator", ","),
        )
        for field in mapping.mappings.get("fields", [])
    )


def _append_events(session, job: ImportJob, action: str, event_type: str, outcome: str) -> None:
    evidence = {
        "status": job.status,
        "totalRows": job.total_rows,
        "validRows": job.valid_rows,
        "invalidRows": job.invalid_rows,
        "failureCode": job.failure_code,
        "mappingVersionId": str(job.selected_mapping_version_id),
        "parserVersion": job.parser_version,
    }
    session.add(
        AuditEvent(
            id=uuid4(),
            workspace_id=job.workspace_id,
            actor_type="system",
            actor_id="import-validator",
            action=action,
            resource_type="import_job",
            resource_id=str(job.id),
            outcome=outcome,
            reason=job.failure_detail,
            evidence=evidence,
        )
    )
    session.add(
        OutboxEvent(
            id=uuid4(),
            workspace_id=job.workspace_id,
            aggregate_type="import_job",
            aggregate_id=str(job.id),
            event_type=event_type,
            event_version=1,
            payload=evidence,
        )
    )
