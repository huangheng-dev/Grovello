from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status

NORTHSTAR_ORGANIZATION_ID = UUID("00000000-0000-4000-8000-000000001001")
NORTHSTAR_WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000001")
SANDBOX_ORGANIZATION_ID = UUID("00000000-0000-4000-8000-000000001002")
SANDBOX_WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000002")


@dataclass(frozen=True, slots=True)
class ActorContext:
    subject_id: str
    session_id: str
    actor_type: str = "human"


@dataclass(frozen=True, slots=True)
class WorkspaceRecord:
    id: UUID
    organization_id: UUID
    slug: str
    name: str
    default_locale: str
    timezone: str
    currency: str


@dataclass(frozen=True, slots=True)
class WorkspaceGrant:
    workspace_id: UUID
    roles: tuple[str, ...]
    permissions: frozenset[str]


@dataclass(frozen=True, slots=True)
class AuthorizedWorkspace:
    actor: ActorContext
    workspace: WorkspaceRecord
    grant: WorkspaceGrant

    def require(self, permission: str) -> None:
        if permission not in self.grant.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission}",
            )


class AccessDirectory:
    """Seed access directory for contract verification before the OIDC adapter is connected."""

    def __init__(
        self,
        workspaces: tuple[WorkspaceRecord, ...],
        grants: dict[tuple[str, UUID], WorkspaceGrant],
    ) -> None:
        self._workspaces = {workspace.id: workspace for workspace in workspaces}
        self._grants = grants

    def visible_workspaces(self, actor: ActorContext) -> list[AuthorizedWorkspace]:
        return [
            AuthorizedWorkspace(actor=actor, workspace=workspace, grant=grant)
            for workspace_id, workspace in self._workspaces.items()
            if (grant := self._grants.get((actor.subject_id, workspace_id))) is not None
        ]

    def authorize(self, actor: ActorContext, workspace_id: UUID) -> AuthorizedWorkspace:
        workspace = self._workspaces.get(workspace_id)
        grant = self._grants.get((actor.subject_id, workspace_id))
        if workspace is None or grant is None:
            # Do not expose whether a workspace exists to an actor outside that tenant.
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
        return AuthorizedWorkspace(actor=actor, workspace=workspace, grant=grant)


WORKSPACES = (
    WorkspaceRecord(
        id=NORTHSTAR_WORKSPACE_ID,
        organization_id=NORTHSTAR_ORGANIZATION_ID,
        slug="northstar-industrial",
        name="Northstar Industrial",
        default_locale="en",
        timezone="Asia/Shanghai",
        currency="USD",
    ),
    WorkspaceRecord(
        id=SANDBOX_WORKSPACE_ID,
        organization_id=SANDBOX_ORGANIZATION_ID,
        slug="global-sandbox",
        name="Global Sandbox",
        default_locale="en",
        timezone="UTC",
        currency="USD",
    ),
)

OWNER_PERMISSIONS = frozenset(
    {
        "workspace.read",
        "workspace.update",
        "workspace.recover",
        "members.read",
        "members.manage",
        "policies.read",
        "policies.manage",
        "audit.read",
        "business_truth.read",
        "business_truth.write",
        "workspace.onboarding.read",
        "workspace.onboarding.write",
        "workspace.onboarding.activate",
        "business_truth.import.read",
        "business_truth.import.create",
        "business_truth.import.map",
        "business_truth.import.apply",
        "business_truth.import.cancel",
        "business_truth.import.compensate",
        "asset.read",
        "asset.download",
        "asset.write",
        "asset.approve",
        "asset.archive",
        "asset.purge",
        "knowledge.retrieve",
        "knowledge.ingest",
        "knowledge.reindex",
        "knowledge.cancel",
        "knowledge.retire",
        "knowledge.sensitive.read",
        "knowledge.admin",
    }
)

access_directory = AccessDirectory(
    workspaces=WORKSPACES,
    grants={
        ("northstar-owner", NORTHSTAR_WORKSPACE_ID): WorkspaceGrant(
            workspace_id=NORTHSTAR_WORKSPACE_ID,
            roles=("workspace_owner",),
            permissions=OWNER_PERMISSIONS,
        ),
        ("northstar-analyst", NORTHSTAR_WORKSPACE_ID): WorkspaceGrant(
            workspace_id=NORTHSTAR_WORKSPACE_ID,
            roles=("growth_analyst",),
            permissions=frozenset(
                {
                    "workspace.read",
                    "members.read",
                    "policies.read",
                    "business_truth.read",
                    "workspace.onboarding.read",
                    "business_truth.import.read",
                    "asset.read",
                    "asset.download",
                    "knowledge.retrieve",
                }
            ),
        ),
        ("sandbox-owner", SANDBOX_WORKSPACE_ID): WorkspaceGrant(
            workspace_id=SANDBOX_WORKSPACE_ID,
            roles=("workspace_owner",),
            permissions=OWNER_PERMISSIONS,
        ),
    },
)
