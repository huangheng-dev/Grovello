from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal, Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from grovello.models import (
    AuditEvent,
    BusinessObject,
    BusinessObjectVersion,
    OutboxEvent,
    Policy,
    Workspace,
    WorkspaceMembership,
    WorkspaceOnboarding,
)

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
    activation_snapshot: dict = field(default_factory=dict)
    activation_business_purpose: str | None = None


@dataclass(frozen=True, slots=True)
class WorkspaceOnboardingMutationResult:
    onboarding: WorkspaceOnboardingRecord
    idempotent_replay: bool


@dataclass(frozen=True, slots=True)
class ActivateWorkspaceOnboardingCommand:
    business_purpose: str
    policy_version: int
    reviewed_warning_codes: tuple[str, ...]


class WorkspaceOnboardingStore(Protocol):
    source: Literal["live"]

    async def create(
        self,
        command: CreateWorkspaceOnboardingCommand,
        context: OnboardingMutationContext,
    ) -> WorkspaceOnboardingMutationResult: ...

    async def get(self) -> WorkspaceOnboardingRecord: ...

    async def activate(
        self,
        command: ActivateWorkspaceOnboardingCommand,
        context: OnboardingMutationContext,
    ) -> WorkspaceOnboardingMutationResult: ...


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

    async def activate(
        self,
        command: ActivateWorkspaceOnboardingCommand,
        context: OnboardingMutationContext,
    ) -> WorkspaceOnboardingMutationResult:
        item = await self._session.scalar(
            select(WorkspaceOnboarding)
            .where(WorkspaceOnboarding.workspace_id == self._workspace_id)
            .with_for_update()
        )
        if item is None:
            raise WorkspaceOnboardingNotFoundError("Workspace business setup was not found")
        if item.activation_idempotency_key is not None:
            if item.activation_idempotency_key != context.idempotency_key:
                raise WorkspaceOnboardingConflictError(
                    "Business profile activation already has another Idempotency-Key"
                )
            if (
                item.policy_version != command.policy_version
                or item.activation_business_purpose != command.business_purpose
                or tuple(item.activation_snapshot.get("reviewedWarningCodes", []))
                != command.reviewed_warning_codes
            ):
                raise WorkspaceOnboardingConflictError(
                    "Idempotency-Key was already used with another activation request"
                )
            return WorkspaceOnboardingMutationResult(self._record(item), True)

        policy = await self._session.scalar(
            select(Policy.id).where(
                Policy.workspace_id == self._workspace_id,
                Policy.version == command.policy_version,
                Policy.status == "active",
            ).limit(1)
        )
        if policy is None:
            raise WorkspaceOnboardingConflictError(
                "The activation policy version is not active in this workspace"
            )

        workspace = await self._session.scalar(
            select(Workspace).where(Workspace.id == self._workspace_id)
        )
        active_objects = tuple(
            (
                await self._session.execute(
                    select(BusinessObject, BusinessObjectVersion)
                    .join(
                        BusinessObjectVersion,
                        (BusinessObjectVersion.object_id == BusinessObject.id)
                        & (BusinessObjectVersion.version == BusinessObject.current_version),
                    )
                    .where(
                        BusinessObject.workspace_id == self._workspace_id,
                        BusinessObject.status == "active",
                        BusinessObjectVersion.status == "active",
                    )
                )
            ).all()
        )
        object_types = {business_object.object_type for business_object, _ in active_objects}
        missing = sorted(set(item.required_object_types) - object_types)
        has_owner = (
            await self._session.scalar(
                select(WorkspaceMembership.id).where(
                    WorkspaceMembership.workspace_id == self._workspace_id,
                    WorkspaceMembership.status == "active",
                ).limit(1)
            )
        ) is not None
        gaps = [
            {
                "code": f"missing_active_{object_type}",
                "severity": "blocking",
                "objectType": object_type,
            }
            for object_type in missing
        ]
        if workspace is None or not all((workspace.default_locale, workspace.timezone, workspace.currency)):
            gaps.append({"code": "workspace_defaults_incomplete", "severity": "blocking"})
        if not has_owner:
            gaps.append({"code": "workspace_owner_missing", "severity": "blocking"})
        warnings = {
            gap.get("code")
            for gap in item.validation_gaps
            if gap.get("severity") == "warning" and gap.get("code")
        }
        if gaps:
            item.status = "blocked"
            item.validation_gaps = gaps
            evidence = {
                "policyVersion": command.policy_version,
                "validationGaps": gaps,
            }
            self._session.add_all(
                [
                    AuditEvent(
                        id=uuid4(), workspace_id=self._workspace_id,
                        actor_type=context.actor_type, actor_id=context.actor_id,
                        session_id=context.session_id, request_id=context.request_id,
                        action="workspace.onboarding.activation_blocked",
                        resource_type="workspace_onboarding", resource_id=str(item.id),
                        outcome="failed", reason="Business profile completeness gate failed",
                        evidence=evidence,
                    ),
                    OutboxEvent(
                        id=uuid4(), workspace_id=self._workspace_id,
                        aggregate_type="workspace_onboarding", aggregate_id=str(item.id),
                        event_type="BusinessProfileActivationBlocked", event_version=1,
                        payload=evidence,
                    ),
                ]
            )
            await self._session.flush()
            await self._session.commit()
            raise WorkspaceOnboardingConflictError(
                "Business profile has blocking completeness gaps"
            )
        if not warnings.issubset(set(command.reviewed_warning_codes)):
            raise WorkspaceOnboardingConflictError(
                "All current profile warnings must be explicitly reviewed"
            )
        now = datetime.now(UTC)
        snapshot = {
            "objectVersions": [
                {
                    "objectType": business_object.object_type,
                    "objectId": str(business_object.id),
                    "versionId": str(version.id),
                    "version": version.version,
                }
                for business_object, version in sorted(
                    active_objects, key=lambda pair: (pair[0].object_type, pair[0].slug)
                )
                if business_object.object_type in item.required_object_types
            ],
            "policyVersion": command.policy_version,
            "reviewedWarningCodes": list(command.reviewed_warning_codes),
            "workspace": {
                "locale": workspace.default_locale,
                "timezone": workspace.timezone,
                "currency": workspace.currency,
            },
        }
        item.status = "active"
        item.validation_gaps = []
        item.last_completed_step = "business_profile_activated"
        item.policy_version = command.policy_version
        item.activation_version += 1
        item.activation_idempotency_key = context.idempotency_key
        item.activation_business_purpose = command.business_purpose
        item.activation_snapshot = snapshot
        item.activated_by = context.actor_id
        item.activated_at = now
        evidence = {
            "activationVersion": item.activation_version,
            "policyVersion": command.policy_version,
            "objectVersions": snapshot["objectVersions"],
        }
        self._session.add_all(
            [
                AuditEvent(
                    id=uuid4(), workspace_id=self._workspace_id,
                    actor_type=context.actor_type, actor_id=context.actor_id,
                    session_id=context.session_id, request_id=context.request_id,
                    action="workspace.onboarding.activated",
                    resource_type="workspace_onboarding", resource_id=str(item.id),
                    outcome="succeeded", reason=command.business_purpose, evidence=evidence,
                ),
                OutboxEvent(
                    id=uuid4(), workspace_id=self._workspace_id,
                    aggregate_type="workspace_onboarding", aggregate_id=str(item.id),
                    event_type="BusinessProfileActivated", event_version=1, payload=evidence,
                ),
            ]
        )
        await self._session.flush()
        await self._session.refresh(item)
        return WorkspaceOnboardingMutationResult(self._record(item), False)

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
            activation_business_purpose=item.activation_business_purpose,
            created_at=item.created_at,
            updated_at=item.updated_at,
            activation_snapshot=item.activation_snapshot,
        )
