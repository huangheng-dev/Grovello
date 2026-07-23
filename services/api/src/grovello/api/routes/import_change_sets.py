from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from grovello.access import AuthorizedWorkspace
from grovello.api.dependencies import (
    get_import_apply_launcher,
    get_import_change_set_store,
    require_idempotency_key,
    require_workspace_access,
)
from grovello.asset_uploads import UploadMutationContext
from grovello.import_change_sets import (
    ApprovalDecisionCommand,
    ChangeSetRecord,
    CreateChangeSetCommand,
    ImportApplyInput,
    ImportApplyLauncher,
    ImportChangeSetConflictError,
    ImportChangeSetNotFoundError,
    ImportChangeSetStore,
    StartCompensationCommand,
)
from grovello.schemas import (
    ApiEnvelope,
    ApiMeta,
    ImportChangeSetApproval,
    ImportChangeSetCreate,
    ImportChangeSetMutationSummary,
    ImportChangeSetOperationSummary,
    ImportChangeSetSummary,
    ImportCompensationRequest,
    ImportWorkflowMutationSummary,
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


def _summary(item: ChangeSetRecord) -> ImportChangeSetSummary:
    return ImportChangeSetSummary(
        id=item.id,
        job_id=item.job_id,
        version=item.version,
        plan_hash=item.plan_hash,
        status=item.status,
        approval_state=item.approval_state,
        approval_policy_version=item.approval_policy_version,
        approval_requested_by=item.approval_requested_by,
        approval_requested_at=item.approval_requested_at,
        approval_decided_by=item.approval_decided_by,
        approval_decided_at=item.approval_decided_at,
        approval_reason=item.approval_reason,
        business_purpose=item.business_purpose,
        summary=item.summary,
        operations=[
            ImportChangeSetOperationSummary(
                id=operation.id,
                source_row_number=operation.source_row_number,
                operation=operation.operation,
                status=operation.status,
                target_object_id=operation.target_object_id,
                expected_version_id=operation.expected_version_id,
                expected_version=operation.expected_version,
                result_object_id=operation.result_object_id,
                result_version_id=operation.result_version_id,
                result_version=operation.result_version,
                failure_code=operation.failure_code,
            )
            for operation in item.operations
        ],
        created_by=item.created_by,
        created_at=item.created_at,
    )


def _raise(error: Exception) -> NoReturn:
    if isinstance(error, ImportChangeSetNotFoundError):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(error, ImportChangeSetConflictError):
        raise HTTPException(status_code=409, detail=str(error)) from error
    raise error


@router.post(
    "/{job_id}/change-set",
    response_model=ApiEnvelope[ImportChangeSetMutationSummary],
    status_code=status.HTTP_201_CREATED,
)
async def create_change_set(
    job_id: UUID,
    payload: ImportChangeSetCreate,
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[ImportChangeSetStore, Depends(get_import_change_set_store)],
    key: Annotated[str, Depends(require_idempotency_key)],
) -> ApiEnvelope[ImportChangeSetMutationSummary]:
    access.require("business_truth.import.apply")
    try:
        result = await store.create(
            job_id,
            CreateChangeSetCommand(payload.business_purpose, payload.policy_version),
            _context(request, access, key),
        )
    except (ImportChangeSetNotFoundError, ImportChangeSetConflictError) as error:
        _raise(error)
    return ApiEnvelope(
        data=ImportChangeSetMutationSummary(
            change_set=_summary(result.change_set),
            idempotent_replay=result.idempotent_replay,
        ),
        meta=ApiMeta(request_id=request.state.request_id),
    )


@router.get(
    "/{job_id}/change-set",
    response_model=ApiEnvelope[ImportChangeSetSummary],
)
async def get_change_set(
    job_id: UUID,
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[ImportChangeSetStore, Depends(get_import_change_set_store)],
) -> ApiEnvelope[ImportChangeSetSummary]:
    access.require("business_truth.import.read")
    try:
        item = await store.get(job_id)
    except (ImportChangeSetNotFoundError, ImportChangeSetConflictError) as error:
        _raise(error)
    return ApiEnvelope(
        data=_summary(item), meta=ApiMeta(request_id=request.state.request_id)
    )


@router.post(
    "/{job_id}/change-set/approval",
    response_model=ApiEnvelope[ImportChangeSetMutationSummary],
)
async def decide_change_set(
    job_id: UUID,
    payload: ImportChangeSetApproval,
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[ImportChangeSetStore, Depends(get_import_change_set_store)],
    key: Annotated[str, Depends(require_idempotency_key)],
) -> ApiEnvelope[ImportChangeSetMutationSummary]:
    access.require("policies.manage")
    access.require("business_truth.import.apply")
    try:
        result = await store.decide(
            job_id,
            ApprovalDecisionCommand(
                payload.decision, payload.reason, payload.policy_version
            ),
            _context(request, access, key),
        )
    except (ImportChangeSetNotFoundError, ImportChangeSetConflictError) as error:
        _raise(error)
    return ApiEnvelope(
        data=ImportChangeSetMutationSummary(
            change_set=_summary(result.change_set),
            idempotent_replay=result.idempotent_replay,
        ),
        meta=ApiMeta(request_id=request.state.request_id),
    )


async def _start(
    job_id: UUID,
    request: Request,
    access: AuthorizedWorkspace,
    store: ImportChangeSetStore,
    launcher: ImportApplyLauncher,
    key: str,
    *,
    compensation: bool,
    compensation_command: StartCompensationCommand | None = None,
) -> ApiEnvelope[ImportWorkflowMutationSummary]:
    try:
        context = _context(request, access, key)
        if compensation:
            if compensation_command is None:
                raise RuntimeError("Compensation policy context is required")
            result = await store.start_compensation(job_id, compensation_command, context)
        else:
            result = await store.start_apply(job_id, context)
        await store.commit()
        await launcher.start(
            result.workflow_id,
            ImportApplyInput(
                workspace_id=str(access.workspace.id),
                job_id=str(job_id),
                change_set_id=str(result.change_set.id),
                actor_type=access.actor.actor_type,
                actor_id=access.actor.subject_id,
                session_id=access.actor.session_id,
                request_id=request.state.request_id,
            ),
        )
    except (ImportChangeSetNotFoundError, ImportChangeSetConflictError) as error:
        _raise(error)
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Import compensation workflow is unavailable"
                if compensation
                else "Import apply workflow is unavailable"
            ),
        ) from error
    return ApiEnvelope(
        data=ImportWorkflowMutationSummary(
            change_set=_summary(result.change_set),
            workflow_id=result.workflow_id,
            idempotent_replay=result.idempotent_replay,
        ),
        meta=ApiMeta(request_id=request.state.request_id),
    )


@router.post(
    "/{job_id}/apply",
    response_model=ApiEnvelope[ImportWorkflowMutationSummary],
    status_code=status.HTTP_202_ACCEPTED,
)
async def apply_change_set(
    job_id: UUID,
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[ImportChangeSetStore, Depends(get_import_change_set_store)],
    launcher: Annotated[ImportApplyLauncher, Depends(get_import_apply_launcher)],
    key: Annotated[str, Depends(require_idempotency_key)],
) -> ApiEnvelope[ImportWorkflowMutationSummary]:
    access.require("business_truth.import.apply")
    access.require("business_truth.write")
    return await _start(job_id, request, access, store, launcher, key, compensation=False)


@router.post(
    "/{job_id}/compensate",
    response_model=ApiEnvelope[ImportWorkflowMutationSummary],
    status_code=status.HTTP_202_ACCEPTED,
)
async def compensate_change_set(
    job_id: UUID,
    payload: ImportCompensationRequest,
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[ImportChangeSetStore, Depends(get_import_change_set_store)],
    launcher: Annotated[ImportApplyLauncher, Depends(get_import_apply_launcher)],
    key: Annotated[str, Depends(require_idempotency_key)],
) -> ApiEnvelope[ImportWorkflowMutationSummary]:
    access.require("business_truth.import.compensate")
    access.require("policies.manage")
    return await _start(
        job_id,
        request,
        access,
        store,
        launcher,
        key,
        compensation=True,
        compensation_command=StartCompensationCommand(
            business_purpose=payload.business_purpose,
            policy_version=payload.policy_version,
        ),
    )
