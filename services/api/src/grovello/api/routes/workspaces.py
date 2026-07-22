from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from grovello.access import ActorContext, AuthorizedWorkspace, access_directory
from grovello.api.dependencies import require_actor, require_workspace_access
from grovello.schemas import (
    ApiEnvelope,
    ApiMeta,
    AuditEventSummary,
    RecoveryPlan,
    WorkspaceAccessSummary,
    WorkspaceSummary,
)

router = APIRouter()


def workspace_summary(access: AuthorizedWorkspace) -> WorkspaceSummary:
    workspace = access.workspace
    return WorkspaceSummary(
        id=str(workspace.id),
        organization_id=str(workspace.organization_id),
        slug=workspace.slug,
        name=workspace.name,
        default_locale=workspace.default_locale,
        timezone=workspace.timezone,
        currency=workspace.currency,
    )


@router.get("", response_model=ApiEnvelope[list[WorkspaceSummary]])
async def list_workspaces(
    request: Request,
    actor: Annotated[ActorContext, Depends(require_actor)],
) -> ApiEnvelope[list[WorkspaceSummary]]:
    data = [workspace_summary(access) for access in access_directory.visible_workspaces(actor)]
    return ApiEnvelope(data=data, meta=ApiMeta(request_id=request.state.request_id, source="seed"))


@router.get("/current/access", response_model=ApiEnvelope[WorkspaceAccessSummary])
async def current_access(
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
) -> ApiEnvelope[WorkspaceAccessSummary]:
    access.require("workspace.read")
    return ApiEnvelope(
        data=WorkspaceAccessSummary(
            workspace=workspace_summary(access),
            subject_id=access.actor.subject_id,
            session_id=access.actor.session_id,
            roles=list(access.grant.roles),
            permissions=sorted(access.grant.permissions),
        ),
        meta=ApiMeta(request_id=request.state.request_id, source="seed"),
    )


@router.get("/{workspace_id}", response_model=ApiEnvelope[WorkspaceSummary])
async def get_workspace(
    workspace_id: UUID,
    request: Request,
    actor: Annotated[ActorContext, Depends(require_actor)],
) -> ApiEnvelope[WorkspaceSummary]:
    access = access_directory.authorize(actor, workspace_id)
    access.require("workspace.read")
    return ApiEnvelope(
        data=workspace_summary(access),
        meta=ApiMeta(request_id=request.state.request_id, source="seed"),
    )


@router.get("/current/audit-events", response_model=ApiEnvelope[list[AuditEventSummary]])
async def audit_events(
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
) -> ApiEnvelope[list[AuditEventSummary]]:
    access.require("audit.read")
    event = AuditEventSummary(
        id="00000000-0000-4000-8000-000000009001",
        workspace_id=str(access.workspace.id),
        actor_type=access.actor.actor_type,
        actor_id=access.actor.subject_id,
        session_id=access.actor.session_id,
        action="workspace.access_reviewed",
        resource_type="Workspace",
        resource_id=str(access.workspace.id),
        outcome="allowed",
        request_id=request.state.request_id,
        evidence={"roles": list(access.grant.roles), "source": "seed-contract"},
    )
    return ApiEnvelope(
        data=[event],
        meta=ApiMeta(request_id=request.state.request_id, source="seed"),
    )


@router.get("/current/recovery-plan", response_model=ApiEnvelope[RecoveryPlan])
async def recovery_plan(
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
) -> ApiEnvelope[RecoveryPlan]:
    access.require("workspace.recover")
    return ApiEnvelope(
        data=RecoveryPlan(
            workspace_id=str(access.workspace.id),
            status="ready",
            required_permission="workspace.recover",
            safeguards=[
                "Verify an active organization owner",
                "Require step-up authentication before mutation",
                "Write an immutable recovery audit event",
                "Revoke affected sessions after recovery",
            ],
        ),
        meta=ApiMeta(request_id=request.state.request_id, source="seed"),
    )
