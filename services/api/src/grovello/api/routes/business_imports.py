from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from grovello.access import AuthorizedWorkspace
from grovello.api.dependencies import (
    get_business_import_store,
    get_import_source_verification_launcher,
    get_import_validation_launcher,
    require_idempotency_key,
    require_workspace_access,
)
from grovello.asset_uploads import UploadMutationContext
from grovello.business_imports import (
    BusinessImportConflictError,
    BusinessImportNotFoundError,
    BusinessImportStore,
    CreateImportJobCommand,
    CreateImportMappingCommand,
    ImportJobRecord,
    ImportSourceVerificationLauncher,
    ImportValidationLauncher,
    StartImportValidationCommand,
)
from grovello.import_validation import FieldMapping
from grovello.schemas import (
    ApiEnvelope,
    ApiMeta,
    ImportIssueSummary,
    ImportJobCreate,
    ImportJobCreateSummary,
    ImportJobMutationSummary,
    ImportJobSummary,
    ImportMappingCreate,
    ImportMappingFieldSummary,
    ImportMappingMutationSummary,
    ImportMappingSummary,
    ImportPreviewRowSummary,
    ImportSourceSummary,
    ImportUploadGrantSummary,
    ImportValidationMutationSummary,
    ImportValidationReportSummary,
    ImportValidationStart,
)

router = APIRouter()


def _context(request: Request, access: AuthorizedWorkspace, key: str) -> UploadMutationContext:
    return UploadMutationContext(
        actor_type=access.actor.actor_type,
        actor_id=access.actor.subject_id,
        session_id=access.actor.session_id,
        request_id=request.state.request_id,
        idempotency_key=key,
    )


def _summary(item: ImportJobRecord) -> ImportJobSummary:
    return ImportJobSummary(
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
        selected_mapping_version_id=item.selected_mapping_version_id,
        validation_workflow_id=item.validation_workflow_id,
        parser_version=item.parser_version,
        input_versions=item.input_versions,
        result_summary=item.result_summary,
        failure_code=item.failure_code,
        failure_detail=item.failure_detail,
        retention_deadline=item.retention_deadline,
        cancelled_at=item.cancelled_at,
        completed_at=item.completed_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
        source=ImportSourceSummary(
            **{field: getattr(item.source, field) for field in item.source.__dataclass_fields__}
        ),
    )


def _mapping_summary(item) -> ImportMappingSummary:
    return ImportMappingSummary(
        id=item.id,
        job_id=item.job_id,
        version=item.version,
        schema_fingerprint=item.schema_fingerprint,
        business_purpose=item.business_purpose,
        source_fields=list(item.source_fields),
        delimiter=item.delimiter,
        fields=[
            ImportMappingFieldSummary(
                source=field.source,
                target=field.target,
                transform=field.transform,
                default_value=field.default_value,
                has_default=field.has_default,
                separator=field.separator,
            )
            for field in item.fields
        ],
        created_by=item.created_by,
        created_at=item.created_at,
    )


def _raise(error: Exception) -> NoReturn:
    if isinstance(error, BusinessImportNotFoundError):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(error, BusinessImportConflictError):
        raise HTTPException(status_code=409, detail=str(error)) from error
    raise error


@router.post(
    "",
    response_model=ApiEnvelope[ImportJobCreateSummary],
    status_code=status.HTTP_201_CREATED,
)
async def create_import_job(
    payload: ImportJobCreate,
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[BusinessImportStore, Depends(get_business_import_store)],
    key: Annotated[str, Depends(require_idempotency_key)],
) -> ApiEnvelope[ImportJobCreateSummary]:
    access.require("business_truth.import.create")
    try:
        result = await store.create(
            CreateImportJobCommand(
                object_type=payload.object_type,
                source_format=payload.source_format,
                schema_version=payload.schema_version,
                locale=payload.locale,
                original_filename=payload.original_filename,
                content_type=payload.content_type,
                content_length=payload.content_length,
                checksum_sha256=payload.checksum_sha256,
                business_purpose=payload.business_purpose,
                input_versions=payload.input_versions,
            ),
            _context(request, access, key),
        )
    except (BusinessImportNotFoundError, BusinessImportConflictError) as error:
        _raise(error)
    return ApiEnvelope(
        data=ImportJobCreateSummary(
            job=_summary(result.job),
            upload=ImportUploadGrantSummary(
                method=result.grant.method.value,
                url=result.grant.url,
                fields=result.grant.fields,
                expires_at=result.grant.expires_at,
            ),
            idempotent_replay=result.idempotent_replay,
        ),
        meta=ApiMeta(request_id=request.state.request_id),
    )


@router.get("", response_model=ApiEnvelope[list[ImportJobSummary]])
async def list_import_jobs(
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[BusinessImportStore, Depends(get_business_import_store)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiEnvelope[list[ImportJobSummary]]:
    access.require("business_truth.import.read")
    return ApiEnvelope(
        data=[_summary(item) for item in await store.list(limit)],
        meta=ApiMeta(request_id=request.state.request_id),
    )


@router.get("/{job_id}", response_model=ApiEnvelope[ImportJobSummary])
async def get_import_job(
    job_id: UUID,
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[BusinessImportStore, Depends(get_business_import_store)],
) -> ApiEnvelope[ImportJobSummary]:
    access.require("business_truth.import.read")
    try:
        item = await store.get(job_id)
    except (BusinessImportNotFoundError, BusinessImportConflictError) as error:
        _raise(error)
    return ApiEnvelope(data=_summary(item), meta=ApiMeta(request_id=request.state.request_id))


@router.post(
    "/{job_id}/complete",
    response_model=ApiEnvelope[ImportJobMutationSummary],
    status_code=status.HTTP_202_ACCEPTED,
)
async def complete_import_source(
    job_id: UUID,
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[BusinessImportStore, Depends(get_business_import_store)],
    launcher: Annotated[ImportSourceVerificationLauncher, Depends(get_import_source_verification_launcher)],
    key: Annotated[str, Depends(require_idempotency_key)],
) -> ApiEnvelope[ImportJobMutationSummary]:
    access.require("business_truth.import.create")
    try:
        result, verification = await store.complete(job_id, _context(request, access, key))
        await store.commit()
        assert result.job.workflow_id is not None
        await launcher.start(result.job.workflow_id, verification)
    except (BusinessImportNotFoundError, BusinessImportConflictError) as error:
        _raise(error)
    except Exception as error:
        raise HTTPException(
            status_code=503, detail="Import source verification workflow is unavailable"
        ) from error
    return ApiEnvelope(
        data=ImportJobMutationSummary(job=_summary(result.job), idempotent_replay=result.idempotent_replay),
        meta=ApiMeta(request_id=request.state.request_id),
    )


@router.post(
    "/{job_id}/mapping",
    response_model=ApiEnvelope[ImportMappingMutationSummary],
    status_code=status.HTTP_201_CREATED,
)
async def create_import_mapping(
    job_id: UUID,
    payload: ImportMappingCreate,
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[BusinessImportStore, Depends(get_business_import_store)],
    key: Annotated[str, Depends(require_idempotency_key)],
) -> ApiEnvelope[ImportMappingMutationSummary]:
    access.require("business_truth.import.map")
    try:
        result = await store.create_mapping(
            job_id,
            CreateImportMappingCommand(
                source_fields=tuple(payload.source_fields),
                delimiter=payload.delimiter,
                fields=tuple(
                    FieldMapping(
                        source=field.source,
                        target=field.target,
                        transform=field.transform,
                        default_value=field.default_value,
                        has_default=field.has_default,
                        separator=field.separator,
                    )
                    for field in payload.fields
                ),
                business_purpose=payload.business_purpose,
            ),
            _context(request, access, key),
        )
    except (BusinessImportNotFoundError, BusinessImportConflictError) as error:
        _raise(error)
    return ApiEnvelope(
        data=ImportMappingMutationSummary(
            mapping=_mapping_summary(result.mapping),
            idempotent_replay=result.idempotent_replay,
        ),
        meta=ApiMeta(request_id=request.state.request_id),
    )


@router.post(
    "/{job_id}/validation",
    response_model=ApiEnvelope[ImportValidationMutationSummary],
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_import_validation(
    job_id: UUID,
    payload: ImportValidationStart,
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[BusinessImportStore, Depends(get_business_import_store)],
    launcher: Annotated[ImportValidationLauncher, Depends(get_import_validation_launcher)],
    key: Annotated[str, Depends(require_idempotency_key)],
) -> ApiEnvelope[ImportValidationMutationSummary]:
    access.require("business_truth.import.map")
    try:
        result = await store.start_validation(
            job_id,
            StartImportValidationCommand(business_purpose=payload.business_purpose),
            _context(request, access, key),
        )
        await store.commit()
        assert result.job.validation_workflow_id is not None
        await launcher.start(result.job.validation_workflow_id, result.payload)
    except (BusinessImportNotFoundError, BusinessImportConflictError) as error:
        _raise(error)
    except Exception as error:
        raise HTTPException(status_code=503, detail="Import validation workflow is unavailable") from error
    return ApiEnvelope(
        data=ImportValidationMutationSummary(
            job=_summary(result.job), idempotent_replay=result.idempotent_replay
        ),
        meta=ApiMeta(request_id=request.state.request_id),
    )


@router.get(
    "/{job_id}/validation",
    response_model=ApiEnvelope[ImportValidationReportSummary],
)
async def get_import_validation_report(
    job_id: UUID,
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[BusinessImportStore, Depends(get_business_import_store)],
    preview_limit: Annotated[int, Query(ge=1, le=500)] = 50,
    issue_limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> ApiEnvelope[ImportValidationReportSummary]:
    access.require("business_truth.import.read")
    try:
        report = await store.validation_report(job_id, preview_limit, issue_limit)
    except (BusinessImportNotFoundError, BusinessImportConflictError) as error:
        _raise(error)
    return ApiEnvelope(
        data=ImportValidationReportSummary(
            job=_summary(report.job),
            mapping=_mapping_summary(report.mapping) if report.mapping else None,
            preview=[
                ImportPreviewRowSummary(
                    source_row_number=row.source_row_number,
                    status=row.status,
                    normalized_data=row.normalized_data,
                    target_identity=row.target_identity,
                )
                for row in report.preview
            ],
            issues=[
                ImportIssueSummary(
                    source_row_number=issue.source_row_number,
                    code=issue.code,
                    severity=issue.severity,
                    field_locator=issue.field_locator,
                    message=issue.message,
                    redacted_sample=issue.redacted_sample,
                )
                for issue in report.issues
            ],
        ),
        meta=ApiMeta(request_id=request.state.request_id),
    )


@router.post(
    "/{job_id}/cancel",
    response_model=ApiEnvelope[ImportJobMutationSummary],
)
async def cancel_import_job(
    job_id: UUID,
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[BusinessImportStore, Depends(get_business_import_store)],
    launcher: Annotated[ImportSourceVerificationLauncher, Depends(get_import_source_verification_launcher)],
    validation_launcher: Annotated[ImportValidationLauncher, Depends(get_import_validation_launcher)],
    key: Annotated[str, Depends(require_idempotency_key)],
) -> ApiEnvelope[ImportJobMutationSummary]:
    access.require("business_truth.import.cancel")
    try:
        result = await store.cancel(job_id, _context(request, access, key))
        await store.commit()
        if result.job.workflow_id:
            await launcher.cancel(result.job.workflow_id)
        if result.job.validation_workflow_id:
            await validation_launcher.cancel(result.job.validation_workflow_id)
    except (BusinessImportNotFoundError, BusinessImportConflictError) as error:
        _raise(error)
    except Exception as error:
        raise HTTPException(status_code=503, detail="Import workflow cancellation is pending") from error
    return ApiEnvelope(
        data=ImportJobMutationSummary(job=_summary(result.job), idempotent_replay=result.idempotent_replay),
        meta=ApiMeta(request_id=request.state.request_id),
    )
