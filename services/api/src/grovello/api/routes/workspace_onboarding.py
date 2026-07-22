from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from grovello.access import AuthorizedWorkspace
from grovello.api.dependencies import (
    get_workspace_onboarding_store,
    require_idempotency_key,
    require_workspace_access,
)
from grovello.schemas import (
    ApiEnvelope,
    ApiMeta,
    WorkspaceOnboardingCreate,
    WorkspaceOnboardingMutationSummary,
    WorkspaceOnboardingSummary,
)
from grovello.workspace_onboarding import (
    CreateWorkspaceOnboardingCommand,
    OnboardingMutationContext,
    WorkspaceOnboardingConflictError,
    WorkspaceOnboardingNotFoundError,
    WorkspaceOnboardingRecord,
    WorkspaceOnboardingStore,
)

router = APIRouter()


def _summary(item: WorkspaceOnboardingRecord) -> WorkspaceOnboardingSummary:
    return WorkspaceOnboardingSummary(
        id=item.id,
        workspace_id=item.workspace_id,
        status=item.status,
        business_purpose=item.business_purpose,
        required_object_types=list(item.required_object_types),
        validation_gaps=list(item.validation_gaps),
        input_versions=item.input_versions,
        last_completed_step=item.last_completed_step,
        policy_version=item.policy_version,
        activation_version=item.activation_version,
        activated_by=item.activated_by,
        activated_at=item.activated_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.post(
    "",
    response_model=ApiEnvelope[WorkspaceOnboardingMutationSummary],
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace_onboarding(
    payload: WorkspaceOnboardingCreate,
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[WorkspaceOnboardingStore, Depends(get_workspace_onboarding_store)],
    key: Annotated[str, Depends(require_idempotency_key)],
) -> ApiEnvelope[WorkspaceOnboardingMutationSummary]:
    access.require("workspace.onboarding.write")
    try:
        result = await store.create(
            CreateWorkspaceOnboardingCommand(
                business_purpose=payload.business_purpose,
                required_object_types=tuple(payload.required_object_types),
                input_versions=payload.input_versions,
            ),
            OnboardingMutationContext(
                actor_type=access.actor.actor_type,
                actor_id=access.actor.subject_id,
                session_id=access.actor.session_id,
                request_id=request.state.request_id,
                idempotency_key=key,
            ),
        )
    except WorkspaceOnboardingConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return ApiEnvelope(
        data=WorkspaceOnboardingMutationSummary(
            onboarding=_summary(result.onboarding),
            idempotent_replay=result.idempotent_replay,
        ),
        meta=ApiMeta(request_id=request.state.request_id),
    )


@router.get("", response_model=ApiEnvelope[WorkspaceOnboardingSummary])
async def get_workspace_onboarding(
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[WorkspaceOnboardingStore, Depends(get_workspace_onboarding_store)],
) -> ApiEnvelope[WorkspaceOnboardingSummary]:
    access.require("workspace.onboarding.read")
    try:
        item = await store.get()
    except WorkspaceOnboardingNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return ApiEnvelope(
        data=_summary(item),
        meta=ApiMeta(request_id=request.state.request_id),
    )
