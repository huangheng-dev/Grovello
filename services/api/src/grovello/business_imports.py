from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from grovello.asset_uploads import UploadMutationContext
from grovello.import_validation import (
    FieldMapping,
    ImportLimits,
    safe_preview,
    schema_fingerprint,
    validate_mapping_definition,
)
from grovello.models import (
    AuditEvent,
    ImportIssue,
    ImportJob,
    ImportMappingVersion,
    ImportRow,
    ImportSource,
    OutboxEvent,
)
from grovello.object_storage import CreateUploadGrantRequest, ObjectStorage, StorageObjectRef, UploadGrant

ImportSourceFormat = Literal["csv", "grovello_json"]
ImportJobStatus = Literal[
    "created",
    "uploading",
    "uploaded",
    "verifying",
    "scanning",
    "ready_for_mapping",
    "mapping",
    "validating",
    "ready_for_review",
    "applying",
    "completed",
    "partially_completed",
    "failed",
    "cancelled",
    "expired",
    "compensating",
    "compensated",
]

IMPORTABLE_OBJECT_TYPES = frozenset(
    {
        "brand",
        "product",
        "offer",
        "price_book",
        "market",
        "icp",
        "evidence",
        "knowledge_document",
        "case_study",
    }
)
SOURCE_CONTENT_TYPES = {
    "csv": "text/csv",
    "grovello_json": "application/json",
}


class BusinessImportError(RuntimeError):
    pass


class BusinessImportNotFoundError(BusinessImportError):
    pass


class BusinessImportConflictError(BusinessImportError):
    pass


@dataclass(frozen=True, slots=True)
class CreateImportJobCommand:
    object_type: str
    source_format: ImportSourceFormat
    schema_version: int
    locale: str
    original_filename: str
    content_type: str
    content_length: int
    checksum_sha256: str
    business_purpose: str
    input_versions: dict


@dataclass(frozen=True, slots=True)
class ImportSourceRecord:
    id: UUID
    state: str
    original_filename: str
    declared_mime_type: str
    declared_size: int
    declared_sha256: str
    verified_size: int | None
    verified_mime_type: str | None
    verified_sha256: str | None
    verified_at: datetime | None
    scan_status: str
    scan_provider: str | None
    scan_reference: str | None
    scan_attempts: int
    scanned_at: datetime | None
    quarantined_at: datetime | None
    expires_at: datetime
    deletion_deadline: datetime
    deleted_at: datetime | None


@dataclass(frozen=True, slots=True)
class ImportJobRecord:
    id: UUID
    workspace_id: UUID
    actor_id: str
    business_purpose: str
    object_type: str
    source_format: ImportSourceFormat
    schema_version: int
    locale: str
    status: ImportJobStatus
    total_rows: int
    valid_rows: int
    invalid_rows: int
    applied_rows: int
    workflow_id: str | None
    input_versions: dict
    result_summary: dict
    failure_code: str | None
    failure_detail: str | None
    retention_deadline: datetime
    cancelled_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    source: ImportSourceRecord
    selected_mapping_version_id: UUID | None = None
    validation_workflow_id: str | None = None
    parser_version: str | None = None


@dataclass(frozen=True, slots=True)
class CreateImportJobResult:
    job: ImportJobRecord
    grant: UploadGrant
    idempotent_replay: bool


@dataclass(frozen=True, slots=True)
class ImportJobMutationResult:
    job: ImportJobRecord
    idempotent_replay: bool


@dataclass(frozen=True, slots=True)
class ImportSourceVerificationInput:
    workspace_id: str
    job_id: str
    source_id: str
    object_key: str
    expected_content_type: str
    expected_content_length: int
    expected_sha256: str


@dataclass(frozen=True, slots=True)
class CreateImportMappingCommand:
    source_fields: tuple[str, ...]
    delimiter: str | None
    fields: tuple[FieldMapping, ...]
    business_purpose: str


@dataclass(frozen=True, slots=True)
class ImportMappingRecord:
    id: UUID
    job_id: UUID
    version: int
    schema_fingerprint: str
    business_purpose: str | None
    source_fields: tuple[str, ...]
    delimiter: str | None
    fields: tuple[FieldMapping, ...]
    created_by: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CreateImportMappingResult:
    mapping: ImportMappingRecord
    idempotent_replay: bool


@dataclass(frozen=True, slots=True)
class ImportValidationInput:
    workspace_id: str
    job_id: str
    mapping_version_id: str


@dataclass(frozen=True, slots=True)
class StartImportValidationCommand:
    business_purpose: str


@dataclass(frozen=True, slots=True)
class ImportValidationStartResult:
    job: ImportJobRecord
    payload: ImportValidationInput
    idempotent_replay: bool


@dataclass(frozen=True, slots=True)
class ImportPreviewRowRecord:
    source_row_number: int
    status: str
    normalized_data: dict
    target_identity: dict


@dataclass(frozen=True, slots=True)
class ImportIssueRecord:
    source_row_number: int | None
    code: str
    severity: str
    field_locator: dict
    message: str
    redacted_sample: str | None


@dataclass(frozen=True, slots=True)
class ImportValidationReportRecord:
    job: ImportJobRecord
    mapping: ImportMappingRecord | None
    preview: tuple[ImportPreviewRowRecord, ...]
    issues: tuple[ImportIssueRecord, ...]


class ImportSourceVerificationLauncher(Protocol):
    async def start(self, workflow_id: str, payload: ImportSourceVerificationInput) -> None: ...

    async def cancel(self, workflow_id: str) -> None: ...


class ImportValidationLauncher(Protocol):
    async def start(self, workflow_id: str, payload: ImportValidationInput) -> None: ...

    async def cancel(self, workflow_id: str) -> None: ...


class BusinessImportStore(Protocol):
    source: Literal["live"]

    async def create(
        self, command: CreateImportJobCommand, context: UploadMutationContext
    ) -> CreateImportJobResult: ...

    async def list(self, limit: int) -> tuple[ImportJobRecord, ...]: ...

    async def get(self, job_id: UUID) -> ImportJobRecord: ...

    async def complete(
        self, job_id: UUID, context: UploadMutationContext
    ) -> tuple[ImportJobMutationResult, ImportSourceVerificationInput]: ...

    async def cancel(self, job_id: UUID, context: UploadMutationContext) -> ImportJobMutationResult: ...

    async def create_mapping(
        self,
        job_id: UUID,
        command: CreateImportMappingCommand,
        context: UploadMutationContext,
    ) -> CreateImportMappingResult: ...

    async def start_validation(
        self,
        job_id: UUID,
        command: StartImportValidationCommand,
        context: UploadMutationContext,
    ) -> ImportValidationStartResult: ...

    async def validation_report(
        self, job_id: UUID, preview_limit: int, issue_limit: int
    ) -> ImportValidationReportRecord: ...

    async def commit(self) -> None: ...


class SqlAlchemyBusinessImportStore:
    source: Literal["live"] = "live"

    def __init__(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        storage: ObjectStorage,
        *,
        max_source_bytes: int,
        upload_ttl_seconds: int,
        max_rows: int = 10_000,
        max_columns: int = 100,
        max_scalar_bytes: int = 65_536,
        max_json_depth: int = 12,
        max_preview_rows: int = 50,
    ) -> None:
        self._session = session
        self._workspace_id = workspace_id
        self._storage = storage
        self._max_source_bytes = max_source_bytes
        self._upload_ttl_seconds = upload_ttl_seconds
        self._mapping_limits = ImportLimits(
            max_source_bytes=max_source_bytes,
            max_rows=max_rows,
            max_columns=max_columns,
            max_scalar_bytes=max_scalar_bytes,
            max_json_depth=max_json_depth,
        )
        self._max_preview_rows = max_preview_rows

    async def create(
        self, command: CreateImportJobCommand, context: UploadMutationContext
    ) -> CreateImportJobResult:
        existing = await self._session.scalar(
            select(ImportJob).where(
                ImportJob.workspace_id == self._workspace_id,
                ImportJob.idempotency_key == context.idempotency_key,
            )
        )
        if existing is not None:
            source = await self._source(existing.id)
            self._assert_same_create(existing, source, command)
            return CreateImportJobResult(self._record(existing, source), await self._grant(source), True)

        self._validate(command)
        now = datetime.now(UTC)
        job_id = uuid4()
        source_id = uuid4()
        item = ImportJob(
            id=job_id,
            workspace_id=self._workspace_id,
            actor_id=context.actor_id,
            session_id=context.session_id,
            request_id=context.request_id,
            idempotency_key=context.idempotency_key,
            business_purpose=command.business_purpose,
            object_type=command.object_type,
            source_format=command.source_format,
            schema_version=command.schema_version,
            locale=command.locale,
            status="uploading",
            input_versions=command.input_versions,
            retention_deadline=now + timedelta(days=30),
        )
        source = ImportSource(
            id=source_id,
            workspace_id=self._workspace_id,
            job_id=job_id,
            state="uploading",
            original_filename=command.original_filename,
            declared_mime_type=command.content_type,
            declared_size=command.content_length,
            declared_sha256=command.checksum_sha256,
            storage_profile="default",
            object_key=f"workspaces/{self._workspace_id}/imports/{job_id}/sources/{source_id}",
            expires_at=now + timedelta(seconds=self._upload_ttl_seconds),
            deletion_deadline=now + timedelta(days=30),
        )
        self._session.add_all([item, source])
        self._append_events(item, context, "business_truth.import.created", "BusinessImportCreated")
        await self._session.flush()
        await self._session.refresh(item)
        await self._session.refresh(source)
        return CreateImportJobResult(self._record(item, source), await self._grant(source), False)

    async def list(self, limit: int) -> tuple[ImportJobRecord, ...]:
        jobs = tuple(
            (
                await self._session.scalars(
                    select(ImportJob)
                    .where(ImportJob.workspace_id == self._workspace_id)
                    .order_by(ImportJob.created_at.desc(), ImportJob.id)
                    .limit(limit)
                )
            ).all()
        )
        return tuple(self._record(job, await self._source(job.id)) for job in jobs)

    async def get(self, job_id: UUID) -> ImportJobRecord:
        item = await self._require(job_id)
        return self._record(item, await self._source(job_id))

    async def complete(
        self, job_id: UUID, context: UploadMutationContext
    ) -> tuple[ImportJobMutationResult, ImportSourceVerificationInput]:
        item = await self._require(job_id, lock=True)
        source = await self._source(job_id, lock=True)
        if item.status == "uploading":
            if source.expires_at <= datetime.now(UTC):
                item.status = "expired"
                source.state = "expired"
                self._append_events(item, context, "business_truth.import.expired", "BusinessImportExpired")
                await self._session.commit()
                raise BusinessImportConflictError("Import source upload has expired")
            item.status = "uploaded"
            source.state = "uploaded"
            item.completion_idempotency_key = context.idempotency_key
            item.workflow_id = f"grovello-import-source-verify-{self._workspace_id}-{item.id}"
            self._append_events(
                item,
                context,
                "business_truth.import.upload_completed",
                "BusinessImportSourceVerificationRequested",
            )
            replay = False
        elif item.status in {"uploaded", "verifying", "scanning", "ready_for_mapping"}:
            if item.completion_idempotency_key != context.idempotency_key:
                raise BusinessImportConflictError("Completion Idempotency-Key does not match")
            replay = True
        else:
            raise BusinessImportConflictError(f"Import source cannot be completed from {item.status}")
        await self._session.flush()
        await self._session.refresh(item)
        await self._session.refresh(source)
        return (
            ImportJobMutationResult(self._record(item, source), replay),
            self._verification_input(item, source),
        )

    async def create_mapping(
        self,
        job_id: UUID,
        command: CreateImportMappingCommand,
        context: UploadMutationContext,
    ) -> CreateImportMappingResult:
        item = await self._require(job_id, lock=True)
        if item.status not in {"ready_for_mapping", "ready_for_review"}:
            raise BusinessImportConflictError(f"Import mapping cannot be created from {item.status}")
        if item.source_format == "csv" and command.delimiter not in {",", ";", "\t", "|"}:
            raise BusinessImportConflictError("CSV mapping requires an allowed explicit delimiter")
        if item.source_format == "grovello_json" and command.delimiter is not None:
            raise BusinessImportConflictError("JSON mappings cannot declare a delimiter")
        try:
            validate_mapping_definition(command.source_fields, command.fields, self._mapping_limits)
        except ValueError as error:
            raise BusinessImportConflictError(str(error)) from error

        existing = await self._session.scalar(
            select(ImportMappingVersion).where(
                ImportMappingVersion.workspace_id == self._workspace_id,
                ImportMappingVersion.job_id == job_id,
                ImportMappingVersion.idempotency_key == context.idempotency_key,
            )
        )
        if existing is not None:
            self._assert_same_mapping(existing, command)
            return CreateImportMappingResult(self._mapping_record(existing), True)

        version = (
            await self._session.scalar(
                select(func.max(ImportMappingVersion.version)).where(
                    ImportMappingVersion.workspace_id == self._workspace_id,
                    ImportMappingVersion.job_id == job_id,
                )
            )
            or 0
        ) + 1
        mapping = ImportMappingVersion(
            id=uuid4(),
            workspace_id=self._workspace_id,
            job_id=job_id,
            version=version,
            schema_fingerprint=schema_fingerprint(item.source_format, command.source_fields),
            idempotency_key=context.idempotency_key,
            business_purpose=command.business_purpose,
            source_fields=list(command.source_fields),
            delimiter=command.delimiter,
            mappings=self._mapping_payload(command.fields),
            created_by=context.actor_id,
        )
        self._session.add(mapping)
        await self._session.flush()
        await self._session.refresh(mapping)
        item.selected_mapping_version_id = mapping.id
        item.status = "ready_for_mapping"
        item.validation_idempotency_key = None
        item.validation_business_purpose = None
        item.validation_workflow_id = None
        item.parser_version = None
        item.total_rows = 0
        item.valid_rows = 0
        item.invalid_rows = 0
        item.result_summary = {}
        self._append_events(
            item,
            context,
            "business_truth.import.mapping_created",
            "BusinessImportMappingCreated",
            extra={
                "mappingVersionId": str(mapping.id),
                "mappingVersion": mapping.version,
                "schemaFingerprint": mapping.schema_fingerprint,
                "businessPurpose": command.business_purpose,
            },
        )
        return CreateImportMappingResult(self._mapping_record(mapping), False)

    async def start_validation(
        self,
        job_id: UUID,
        command: StartImportValidationCommand,
        context: UploadMutationContext,
    ) -> ImportValidationStartResult:
        item = await self._require(job_id, lock=True)
        source = await self._source(job_id, lock=True)
        if item.selected_mapping_version_id is None:
            raise BusinessImportConflictError("Import validation requires an immutable mapping")
        if source.state != "clean" or source.scan_status != "clean":
            raise BusinessImportConflictError("Import source is not verified and clean")
        if item.status == "ready_for_mapping":
            item.status = "validating"
            item.validation_idempotency_key = context.idempotency_key
            item.validation_business_purpose = command.business_purpose
            item.validation_workflow_id = (
                f"grovello-import-validate-{self._workspace_id}-{item.id}-{item.selected_mapping_version_id}"
            )
            self._append_events(
                item,
                context,
                "business_truth.import.validation_requested",
                "BusinessImportValidationRequested",
                extra={"businessPurpose": command.business_purpose},
            )
            replay = False
        elif item.status in {"validating", "ready_for_review"}:
            if item.validation_idempotency_key != context.idempotency_key:
                raise BusinessImportConflictError("Validation Idempotency-Key does not match")
            if item.validation_business_purpose != command.business_purpose:
                raise BusinessImportConflictError(
                    "Validation Idempotency-Key was already used with another business purpose"
                )
            replay = True
        else:
            raise BusinessImportConflictError(f"Import validation cannot be started from {item.status}")
        await self._session.flush()
        await self._session.refresh(item)
        assert item.validation_workflow_id is not None
        return ImportValidationStartResult(
            job=self._record(item, source),
            payload=ImportValidationInput(
                workspace_id=str(self._workspace_id),
                job_id=str(item.id),
                mapping_version_id=str(item.selected_mapping_version_id),
            ),
            idempotent_replay=replay,
        )

    async def validation_report(
        self, job_id: UUID, preview_limit: int, issue_limit: int
    ) -> ImportValidationReportRecord:
        preview_limit = min(preview_limit, self._max_preview_rows)
        item = await self._require(job_id)
        source = await self._source(job_id)
        mapping = None
        rows: tuple[ImportRow, ...] = ()
        if item.selected_mapping_version_id is not None:
            mapping = await self._session.scalar(
                select(ImportMappingVersion).where(
                    ImportMappingVersion.workspace_id == self._workspace_id,
                    ImportMappingVersion.id == item.selected_mapping_version_id,
                    ImportMappingVersion.job_id == job_id,
                )
            )
            rows = tuple(
                (
                    await self._session.scalars(
                        select(ImportRow)
                        .where(
                            ImportRow.workspace_id == self._workspace_id,
                            ImportRow.job_id == job_id,
                            ImportRow.mapping_version_id == item.selected_mapping_version_id,
                        )
                        .order_by(ImportRow.source_row_number)
                        .limit(preview_limit)
                    )
                ).all()
            )
        issue_rows: tuple[tuple[ImportIssue, int], ...] = ()
        if item.selected_mapping_version_id is not None:
            issue_rows = tuple(
                (
                    await self._session.execute(
                        select(ImportIssue, ImportRow.source_row_number)
                        .join(ImportRow, ImportRow.id == ImportIssue.row_id)
                        .where(
                            ImportIssue.workspace_id == self._workspace_id,
                            ImportIssue.job_id == job_id,
                            ImportRow.mapping_version_id == item.selected_mapping_version_id,
                        )
                        .order_by(ImportRow.source_row_number, ImportIssue.created_at, ImportIssue.id)
                        .limit(issue_limit)
                    )
                ).all()
            )
        return ImportValidationReportRecord(
            job=self._record(item, source),
            mapping=self._mapping_record(mapping) if mapping else None,
            preview=tuple(
                ImportPreviewRowRecord(
                    source_row_number=row.source_row_number,
                    status=row.status,
                    normalized_data=safe_preview(row.normalized_data),
                    target_identity=row.target_identity,
                )
                for row in rows
            ),
            issues=tuple(
                ImportIssueRecord(
                    source_row_number=source_row_number,
                    code=issue.code,
                    severity=issue.severity,
                    field_locator=issue.field_locator,
                    message=issue.message,
                    redacted_sample=issue.redacted_sample,
                )
                for issue, source_row_number in issue_rows
            ),
        )

    async def cancel(self, job_id: UUID, context: UploadMutationContext) -> ImportJobMutationResult:
        item = await self._require(job_id, lock=True)
        source = await self._source(job_id, lock=True)
        if item.status == "cancelled":
            if item.cancellation_idempotency_key != context.idempotency_key:
                raise BusinessImportConflictError("Cancellation Idempotency-Key does not match")
            return ImportJobMutationResult(self._record(item, source), True)
        if item.status not in {
            "created",
            "uploading",
            "uploaded",
            "verifying",
            "scanning",
            "ready_for_mapping",
            "mapping",
            "validating",
            "ready_for_review",
        }:
            raise BusinessImportConflictError(f"Import job cannot be cancelled from {item.status}")
        item.status = "cancelled"
        item.cancellation_idempotency_key = context.idempotency_key
        item.cancelled_at = datetime.now(UTC)
        source.state = "cancelled"
        self._append_events(item, context, "business_truth.import.cancelled", "BusinessImportCancelled")
        await self._session.flush()
        await self._session.refresh(item)
        await self._session.refresh(source)
        return ImportJobMutationResult(self._record(item, source), False)

    async def commit(self) -> None:
        await self._session.commit()

    async def _require(self, job_id: UUID, *, lock: bool = False) -> ImportJob:
        statement = select(ImportJob).where(
            ImportJob.workspace_id == self._workspace_id, ImportJob.id == job_id
        )
        if lock:
            statement = statement.with_for_update()
        item = await self._session.scalar(statement)
        if item is None:
            raise BusinessImportNotFoundError("Import job was not found")
        return item

    async def _source(self, job_id: UUID, *, lock: bool = False) -> ImportSource:
        statement = select(ImportSource).where(
            ImportSource.workspace_id == self._workspace_id, ImportSource.job_id == job_id
        )
        if lock:
            statement = statement.with_for_update()
        source = await self._session.scalar(statement)
        if source is None:
            raise BusinessImportNotFoundError("Import source was not found")
        return source

    def _validate(self, command: CreateImportJobCommand) -> None:
        if command.object_type not in IMPORTABLE_OBJECT_TYPES:
            raise BusinessImportConflictError("Object type is not importable in P2-D1")
        if SOURCE_CONTENT_TYPES.get(command.source_format) != command.content_type:
            raise BusinessImportConflictError("Source format and content type do not match")
        if command.content_length <= 0 or command.content_length > self._max_source_bytes:
            raise BusinessImportConflictError("Import source exceeds the configured size limit")

    def _assert_same_create(
        self, item: ImportJob, source: ImportSource, command: CreateImportJobCommand
    ) -> None:
        if not all(
            (
                item.object_type == command.object_type,
                item.source_format == command.source_format,
                item.schema_version == command.schema_version,
                item.locale == command.locale,
                item.business_purpose == command.business_purpose,
                item.input_versions == command.input_versions,
                source.original_filename == command.original_filename,
                source.declared_mime_type == command.content_type,
                source.declared_size == command.content_length,
                source.declared_sha256 == command.checksum_sha256,
            )
        ):
            raise BusinessImportConflictError("Idempotency-Key was already used with another request")

    async def _grant(self, source: ImportSource) -> UploadGrant:
        if source.state != "uploading" or source.expires_at <= datetime.now(UTC):
            raise BusinessImportConflictError("Import source no longer accepts uploads")
        remaining = max(
            1,
            min(
                self._upload_ttl_seconds,
                int((source.expires_at - datetime.now(UTC)).total_seconds()),
            ),
        )
        return await self._storage.create_upload_grant(
            CreateUploadGrantRequest(
                destination=StorageObjectRef(self._workspace_id, source.object_key, source.storage_profile),
                content_type=source.declared_mime_type,
                content_length=source.declared_size,
                checksum_sha256=source.declared_sha256,
                expires_in_seconds=remaining,
            )
        )

    def _append_events(
        self,
        item: ImportJob,
        context: UploadMutationContext,
        action: str,
        event_type: str,
        *,
        extra: dict | None = None,
    ) -> None:
        evidence = {
            "status": item.status,
            "objectType": item.object_type,
            "sourceFormat": item.source_format,
            "businessPurpose": item.business_purpose,
        }
        if extra:
            evidence.update(extra)
        self._session.add(
            AuditEvent(
                id=uuid4(),
                workspace_id=self._workspace_id,
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                session_id=context.session_id,
                request_id=context.request_id,
                action=action,
                resource_type="import_job",
                resource_id=str(item.id),
                outcome="succeeded",
                evidence=evidence,
            )
        )
        self._session.add(
            OutboxEvent(
                id=uuid4(),
                workspace_id=self._workspace_id,
                aggregate_type="import_job",
                aggregate_id=str(item.id),
                event_type=event_type,
                event_version=1,
                payload={"status": item.status, "workflowId": item.workflow_id},
            )
        )

    @staticmethod
    def _mapping_payload(fields: tuple[FieldMapping, ...]) -> dict:
        return {
            "contractVersion": 1,
            "fields": [
                {
                    "source": field.source,
                    "target": field.target,
                    "transform": field.transform,
                    "defaultValue": field.default_value,
                    "hasDefault": field.has_default,
                    "separator": field.separator,
                }
                for field in fields
            ],
        }

    @staticmethod
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

    @classmethod
    def _mapping_record(cls, mapping: ImportMappingVersion) -> ImportMappingRecord:
        return ImportMappingRecord(
            id=mapping.id,
            job_id=mapping.job_id,
            version=mapping.version,
            schema_fingerprint=mapping.schema_fingerprint,
            business_purpose=mapping.business_purpose,
            source_fields=tuple(mapping.source_fields),
            delimiter=mapping.delimiter,
            fields=cls._mapping_fields(mapping),
            created_by=mapping.created_by,
            created_at=mapping.created_at,
        )

    @classmethod
    def _assert_same_mapping(cls, mapping: ImportMappingVersion, command: CreateImportMappingCommand) -> None:
        if not all(
            (
                tuple(mapping.source_fields) == command.source_fields,
                mapping.delimiter == command.delimiter,
                mapping.mappings == cls._mapping_payload(command.fields),
                mapping.business_purpose == command.business_purpose,
            )
        ):
            raise BusinessImportConflictError("Idempotency-Key was already used with another mapping")

    def _verification_input(self, item: ImportJob, source: ImportSource) -> ImportSourceVerificationInput:
        return ImportSourceVerificationInput(
            workspace_id=str(self._workspace_id),
            job_id=str(item.id),
            source_id=str(source.id),
            object_key=source.object_key,
            expected_content_type=source.declared_mime_type,
            expected_content_length=source.declared_size,
            expected_sha256=source.declared_sha256,
        )

    @staticmethod
    def _record(item: ImportJob, source: ImportSource) -> ImportJobRecord:
        return ImportJobRecord(
            id=item.id,
            workspace_id=item.workspace_id,
            actor_id=item.actor_id,
            business_purpose=item.business_purpose,
            object_type=item.object_type,
            source_format=item.source_format,
            schema_version=item.schema_version,
            locale=item.locale,
            status=item.status,
            total_rows=item.total_rows,
            valid_rows=item.valid_rows,
            invalid_rows=item.invalid_rows,
            applied_rows=item.applied_rows,
            workflow_id=item.workflow_id,
            input_versions=item.input_versions,
            result_summary=item.result_summary,
            failure_code=item.failure_code,
            failure_detail=item.failure_detail,
            retention_deadline=item.retention_deadline,
            cancelled_at=item.cancelled_at,
            completed_at=item.completed_at,
            created_at=item.created_at,
            updated_at=item.updated_at,
            source=ImportSourceRecord(
                id=source.id,
                state=source.state,
                original_filename=source.original_filename,
                declared_mime_type=source.declared_mime_type,
                declared_size=source.declared_size,
                declared_sha256=source.declared_sha256,
                verified_size=source.verified_size,
                verified_mime_type=source.verified_mime_type,
                verified_sha256=source.verified_sha256,
                verified_at=source.verified_at,
                scan_status=source.scan_status,
                scan_provider=source.scan_provider,
                scan_reference=source.scan_reference,
                scan_attempts=source.scan_attempts,
                scanned_at=source.scanned_at,
                quarantined_at=source.quarantined_at,
                expires_at=source.expires_at,
                deletion_deadline=source.deletion_deadline,
                deleted_at=source.deleted_at,
            ),
            selected_mapping_version_id=item.selected_mapping_version_id,
            validation_workflow_id=item.validation_workflow_id,
            parser_version=item.parser_version,
        )
