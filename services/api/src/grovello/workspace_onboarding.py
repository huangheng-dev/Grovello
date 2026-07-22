from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from grovello.models import AuditEvent, OutboxEvent, WorkspaceOnboarding

WorkspaceOnboardingStatus = Literal[
    "draft", "in_progress", "ready_for_review", "active", "blocked"
]


class WorkspaceOnboardingNotFoundError(LookupError):
    pass


class WorkspaceOnboardingConflictError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class OnboardingMutationContext:
    actor_type: str
    actor_id: str
    session_id: str
    request_id: str
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class CreateWorkspaceOnboardingCommand:
    business_purpose: str
    required_object_types: tuple[str, ...]
    input_versions: dict


@dataclass(frozen=True, slots=True)
class WorkspaceOnboardingRecord:
    id: UUID
    workspace_id: UUID
    status: WorkspaceOnboardingStatus
    business_purpose: str
    required_object_types: tuple[str, ...]
    validation_gaps: tuple[dict, ...]
    input_versions: dict
    last_completed_step: str | None
    policy_version: int | None
    activation_version: int
    activated_by: str | None
    activated_at: object | None
    created_at: object
    updated_at: object


@dataclass(frozen=True, slots=True)
class WorkspaceOnboardingMutationResult:
    onboarding: WorkspaceOnboardingRecord
    idempotent_replay: bool


class WorkspaceOnboardingStore(Protocol):
    source: Literal["live"]

    async def create(
        self,
        command: CreateWorkspaceOnboardingCommand,
        context: OnboardingMutationContext,
    ) -> WorkspaceOnboardingMutationResult: ...

    async def get(self) -> WorkspaceOnboardingRecord: ...


class SqlAlchemyWorkspaceOnboardingStore:
    source: Literal["live"] = "live"

    def __init__(self, session: AsyncSession, workspace_id: UUID) -> None:
        self._session = session
        self._workspace_id = workspace_id

    async def create(
        self,
        command: CreateWorkspaceOnboardingCommand,
        context: OnboardingMutationContext,
    ) -> WorkspaceOnboardingMutationResult:
        existing = await self._session.scalar(
            select(WorkspaceOnboarding).where(
                WorkspaceOnboarding.workspace_id == self._workspace_id
            )
        )
        if existing is not None:
            if existing.idempotency_key != context.idempotency_key:
                raise WorkspaceOnboardingConflictError(
                    "Workspace business setup already exists"
                )
            if (
                existing.business_purpose != command.business_purpose
                or tuple(existing.required_object_types) != command.required_object_types
                or existing.input_versions != command.input_versions
            ):
                raise WorkspaceOnboardingConflictError(
                    "Idempotency-Key was already used with another request"
                )
            return WorkspaceOnboardingMutationResult(self._record(existing), True)

        item = WorkspaceOnboarding(
            id=uuid4(),
            workspace_id=self._workspace_id,
            actor_id=context.actor_id,
            session_id=context.session_id,
            request_id=context.request_id,
            idempotency_key=context.idempotency_key,
            business_purpose=command.business_purpose,
            status="draft",
            required_object_types=list(command.required_object_types),
            validation_gaps=[],
            input_versions=command.input_versions,
        )
        self._session.add(item)
        self._session.add(
            AuditEvent(
                id=uuid4(),
                workspace_id=self._workspace_id,
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                session_id=context.session_id,
                request_id=context.request_id,
                action="workspace.onboarding.created",
                resource_type="workspace_onboarding",
                resource_id=str(item.id),
                outcome="succeeded",
                evidence={"status": item.status, "businessPurpose": item.business_purpose},
            )
        )
        self._session.add(
            OutboxEvent(
                id=uuid4(),
                workspace_id=self._workspace_id,
                aggregate_type="workspace_onboarding",
                aggregate_id=str(item.id),
                event_type="WorkspaceOnboardingCreated",
                event_version=1,
                payload={"status": item.status},
            )
        )
        await self._session.flush()
        await self._session.refresh(item)
        return WorkspaceOnboardingMutationResult(self._record(item), False)

    async def get(self) -> WorkspaceOnboardingRecord:
        item = await self._session.scalar(
            select(WorkspaceOnboarding).where(
                WorkspaceOnboarding.workspace_id == self._workspace_id
            )
        )
        if item is None:
            raise WorkspaceOnboardingNotFoundError("Workspace business setup was not found")
        return self._record(item)

    @staticmethod
    def _record(item: WorkspaceOnboarding) -> WorkspaceOnboardingRecord:
        return WorkspaceOnboardingRecord(
            id=item.id,
            workspace_id=item.workspace_id,
            status=item.status,
            business_purpose=item.business_purpose,
            required_object_types=tuple(item.required_object_types),
            validation_gaps=tuple(item.validation_gaps),
            input_versions=item.input_versions,
            last_completed_step=item.last_completed_step,
            policy_version=item.policy_version,
            activation_version=item.activation_version,
            activated_by=item.activated_by,
            activated_at=item.activated_at,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
