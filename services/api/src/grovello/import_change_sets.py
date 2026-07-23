import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from grovello.asset_uploads import UploadMutationContext
from grovello.models import (
    AuditEvent,
    BusinessObject,
    BusinessObjectVersion,
    ImportChangeSet,
    ImportChangeSetOperation,
    ImportJob,
    ImportRow,
    OutboxEvent,
    Policy,
)


class ImportChangeSetNotFoundError(LookupError):
    pass


class ImportChangeSetConflictError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CreateChangeSetCommand:
    business_purpose: str
    policy_version: int | None


@dataclass(frozen=True, slots=True)
class ApprovalDecisionCommand:
    decision: Literal["approved", "rejected"]
    reason: str
    policy_version: int


@dataclass(frozen=True, slots=True)
class StartCompensationCommand:
    business_purpose: str
    policy_version: int


@dataclass(frozen=True, slots=True)
class ChangeSetOperationRecord:
    id: UUID
    source_row_number: int
    operation: str
    status: str
    target_object_id: UUID | None
    expected_version_id: UUID | None
    expected_version: int | None
    result_object_id: UUID | None
    result_version_id: UUID | None
    result_version: int | None
    failure_code: str | None


@dataclass(frozen=True, slots=True)
class ChangeSetRecord:
    id: UUID
    job_id: UUID
    version: int
    plan_hash: str
    status: str
    approval_state: str
    approval_policy_version: int | None
    approval_requested_by: str | None
    approval_requested_at: datetime | None
    approval_decided_by: str | None
    approval_decided_at: datetime | None
    approval_reason: str | None
    business_purpose: str
    summary: dict
    operations: tuple[ChangeSetOperationRecord, ...]
    created_by: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ChangeSetMutationResult:
    change_set: ChangeSetRecord
    idempotent_replay: bool


@dataclass(frozen=True, slots=True)
class ImportApplyInput:
    workspace_id: str
    job_id: str
    change_set_id: str
    actor_type: str
    actor_id: str
    session_id: str | None
    request_id: str | None


@dataclass(frozen=True, slots=True)
class ImportWorkflowStartResult:
    change_set: ChangeSetRecord
    workflow_id: str
    idempotent_replay: bool


class ImportApplyLauncher(Protocol):
    async def start(self, workflow_id: str, payload: ImportApplyInput) -> None: ...

    async def cancel(self, workflow_id: str) -> None: ...


class ImportChangeSetStore(Protocol):
    async def create(
        self, job_id: UUID, command: CreateChangeSetCommand, context: UploadMutationContext
    ) -> ChangeSetMutationResult: ...

    async def get(self, job_id: UUID) -> ChangeSetRecord: ...

    async def decide(
        self,
        job_id: UUID,
        command: ApprovalDecisionCommand,
        context: UploadMutationContext,
    ) -> ChangeSetMutationResult: ...

    async def start_apply(
        self, job_id: UUID, context: UploadMutationContext
    ) -> ImportWorkflowStartResult: ...

    async def start_compensation(
        self,
        job_id: UUID,
        command: StartCompensationCommand,
        context: UploadMutationContext,
    ) -> ImportWorkflowStartResult: ...

    async def commit(self) -> None: ...


class SqlAlchemyImportChangeSetStore:
    def __init__(self, session: AsyncSession, workspace_id: UUID) -> None:
        self._session = session
        self._workspace_id = workspace_id

    async def create(
        self, job_id: UUID, command: CreateChangeSetCommand, context: UploadMutationContext
    ) -> ChangeSetMutationResult:
        job = await self._job(job_id, lock=True)
        existing = await self._session.scalar(
            select(ImportChangeSet).where(
                ImportChangeSet.workspace_id == self._workspace_id,
                ImportChangeSet.job_id == job_id,
                ImportChangeSet.idempotency_key == context.idempotency_key,
            )
        )
        if existing is not None:
            if existing.business_purpose != command.business_purpose:
                raise ImportChangeSetConflictError(
                    "Idempotency-Key was already used with another change-set request"
                )
            return ChangeSetMutationResult(await self._record(existing), True)
        if job.status != "ready_for_review":
            raise ImportChangeSetConflictError(
                f"Change set cannot be planned from import status {job.status}"
            )
        rows = tuple(
            (
                await self._session.scalars(
                    select(ImportRow)
                    .where(
                        ImportRow.workspace_id == self._workspace_id,
                        ImportRow.job_id == job_id,
                    )
                    .order_by(ImportRow.source_row_number)
                )
            ).all()
        )
        if not rows:
            raise ImportChangeSetConflictError("Validated import contains no rows")

        prior_sets = tuple(
            (
                await self._session.scalars(
                    select(ImportChangeSet).where(
                        ImportChangeSet.workspace_id == self._workspace_id,
                        ImportChangeSet.job_id == job_id,
                    )
                )
            ).all()
        )
        version = max((item.version for item in prior_sets), default=0) + 1
        plan: list[dict] = []
        active_count = 0
        for sequence, row in enumerate(rows, start=1):
            operation, target_id, expected_id, expected_version = await self._plan_row(row)
            if operation in {"create", "new_version"} and row.normalized_data.get("status") == "active":
                active_count += 1
            plan.append(
                {
                    "sequence": sequence,
                    "rowId": str(row.id),
                    "sourceRowNumber": row.source_row_number,
                    "contentHash": row.content_hash,
                    "operation": operation,
                    "targetObjectId": str(target_id) if target_id else None,
                    "expectedVersionId": str(expected_id) if expected_id else None,
                    "expectedVersion": expected_version,
                    "input": row.normalized_data,
                }
            )
        plan_hash = _hash_plan(job, version, plan)
        if active_count and command.policy_version is None:
            raise ImportChangeSetConflictError(
                "Active-version change sets require an explicit policy version"
            )
        if active_count:
            await self._require_policy_version(command.policy_version)
        change_set = ImportChangeSet(
            id=uuid4(),
            workspace_id=self._workspace_id,
            job_id=job_id,
            version=version,
            plan_hash=plan_hash,
            status="ready_for_review",
            expected_inputs={
                "mappingVersionId": str(job.selected_mapping_version_id),
                "parserVersion": job.parser_version,
                "sourceChecksum": job.input_versions.get("sourceChecksum"),
            },
            summary=_summary(plan),
            approval_state="pending" if active_count else "not_required",
            idempotency_key=context.idempotency_key,
            business_purpose=command.business_purpose,
            approval_policy_version=command.policy_version,
            approval_requested_by=context.actor_id if active_count else None,
            approval_requested_at=datetime.now(UTC) if active_count else None,
            created_by=context.actor_id,
        )
        self._session.add(change_set)
        for item in plan:
            operation = ImportChangeSetOperation(
                id=uuid4(),
                workspace_id=self._workspace_id,
                change_set_id=change_set.id,
                row_id=UUID(item["rowId"]),
                sequence=item["sequence"],
                operation_key=_operation_key(
                    self._workspace_id, job_id, item["rowId"], version
                ),
                operation=item["operation"],
                status=(
                    "skipped"
                    if item["operation"] == "skip"
                    else "failed"
                    if item["operation"] == "conflict"
                    else "planned"
                ),
                target_object_id=UUID(item["targetObjectId"]) if item["targetObjectId"] else None,
                expected_version_id=(
                    UUID(item["expectedVersionId"]) if item["expectedVersionId"] else None
                ),
                expected_version=item["expectedVersion"],
                input_snapshot=item["input"],
                failure_code="unresolved_identity_conflict" if item["operation"] == "conflict" else None,
            )
            self._session.add(operation)
        for item in prior_sets:
            if item.status in {"draft", "ready_for_review", "approved"}:
                item.status = "superseded"
        job.dry_run_plan_hash = plan_hash
        job.selected_change_set_id = change_set.id
        self._append_lineage(
            job,
            change_set,
            context,
            "business_truth.import.change_set_created",
            "BusinessImportChangeSetCreated",
        )
        await self._session.flush()
        return ChangeSetMutationResult(await self._record(change_set), False)

    async def get(self, job_id: UUID) -> ChangeSetRecord:
        item = await self._current(job_id)
        return await self._record(item)

    async def decide(
        self,
        job_id: UUID,
        command: ApprovalDecisionCommand,
        context: UploadMutationContext,
    ) -> ChangeSetMutationResult:
        change_set = await self._current(job_id, lock=True)
        if change_set.approval_state == command.decision:
            if (
                change_set.approval_idempotency_key != context.idempotency_key
                or
                change_set.approval_policy_version != command.policy_version
                or change_set.approval_reason != command.reason
            ):
                raise ImportChangeSetConflictError("Approval decision does not match the earlier decision")
            return ChangeSetMutationResult(await self._record(change_set), True)
        if change_set.approval_state != "pending":
            raise ImportChangeSetConflictError(
                f"Change set approval cannot be decided from {change_set.approval_state}"
            )
        if change_set.approval_policy_version != command.policy_version:
            raise ImportChangeSetConflictError(
                "Approval policy version must match the reviewed change set"
            )
        await self._require_policy_version(command.policy_version)
        change_set.approval_state = command.decision
        change_set.status = "approved" if command.decision == "approved" else "rejected"
        change_set.approval_policy_version = command.policy_version
        change_set.approval_decided_by = context.actor_id
        change_set.approval_decided_at = datetime.now(UTC)
        change_set.approval_reason = command.reason
        change_set.approval_idempotency_key = context.idempotency_key
        job = await self._job(job_id)
        self._append_lineage(
            job,
            change_set,
            context,
            f"business_truth.import.change_set_{command.decision}",
            f"BusinessImportChangeSet{command.decision.title()}",
        )
        await self._session.flush()
        return ChangeSetMutationResult(await self._record(change_set), False)

    async def start_apply(
        self, job_id: UUID, context: UploadMutationContext
    ) -> ImportWorkflowStartResult:
        job = await self._job(job_id, lock=True)
        change_set = await self._current(job_id, lock=True)
        if job.apply_idempotency_key is not None:
            if job.apply_idempotency_key != context.idempotency_key:
                raise ImportChangeSetConflictError("Import apply already has another Idempotency-Key")
            assert job.apply_workflow_id is not None
            return ImportWorkflowStartResult(
                await self._record(change_set), job.apply_workflow_id, True
            )
        if job.status != "ready_for_review":
            raise ImportChangeSetConflictError(f"Import cannot apply from status {job.status}")
        if change_set.summary.get("conflict", 0):
            raise ImportChangeSetConflictError("Change set has unresolved identity conflicts")
        if change_set.approval_state not in {"not_required", "approved"}:
            raise ImportChangeSetConflictError("Change set requires an approved policy decision")
        if change_set.approval_state == "approved":
            await self._require_policy_version(change_set.approval_policy_version)
        await self._verify_expected_versions(change_set.id)
        workflow_id = f"grovello-import-apply-{self._workspace_id}-{job.id}-v{change_set.version}"
        job.status = "applying"
        job.apply_idempotency_key = context.idempotency_key
        job.apply_workflow_id = workflow_id
        self._append_lineage(
            job,
            change_set,
            context,
            "business_truth.import.apply_started",
            "BusinessImportApplyStarted",
        )
        await self._session.flush()
        return ImportWorkflowStartResult(await self._record(change_set), workflow_id, False)

    async def start_compensation(
        self,
        job_id: UUID,
        command: StartCompensationCommand,
        context: UploadMutationContext,
    ) -> ImportWorkflowStartResult:
        job = await self._job(job_id, lock=True)
        change_set = await self._current(job_id, lock=True)
        if job.compensation_idempotency_key is not None:
            if job.compensation_idempotency_key != context.idempotency_key:
                raise ImportChangeSetConflictError(
                    "Import compensation already has another Idempotency-Key"
                )
            if (
                job.compensation_policy_version != command.policy_version
                or job.compensation_business_purpose != command.business_purpose
            ):
                raise ImportChangeSetConflictError(
                    "Idempotency-Key was already used with another compensation request"
                )
            assert job.compensation_workflow_id is not None
            return ImportWorkflowStartResult(
                await self._record(change_set), job.compensation_workflow_id, True
            )
        if job.status not in {"completed", "partially_completed"}:
            raise ImportChangeSetConflictError(
                f"Import cannot be compensated from status {job.status}"
            )
        await self._require_policy_version(command.policy_version)
        workflow_id = f"grovello-import-compensate-{self._workspace_id}-{job.id}-v{change_set.version}"
        job.status = "compensating"
        job.compensation_idempotency_key = context.idempotency_key
        job.compensation_workflow_id = workflow_id
        job.compensation_policy_version = command.policy_version
        job.compensation_business_purpose = command.business_purpose
        self._append_lineage(
            job,
            change_set,
            context,
            "business_truth.import.compensation_started",
            "BusinessImportCompensationStarted",
        )
        await self._session.flush()
        return ImportWorkflowStartResult(await self._record(change_set), workflow_id, False)

    async def commit(self) -> None:
        await self._session.commit()

    async def _plan_row(
        self, row: ImportRow
    ) -> tuple[str, UUID | None, UUID | None, int | None]:
        if row.status in {"invalid", "duplicate"}:
            return "skip", None, None, None
        if row.status == "conflict":
            return "conflict", None, None, None
        object_id = row.target_identity.get("objectId")
        version_id = row.target_identity.get("currentVersionId")
        if not object_id:
            return "create", None, None, None
        target = await self._session.scalar(
            select(BusinessObject).where(
                BusinessObject.workspace_id == self._workspace_id,
                BusinessObject.id == UUID(object_id),
            )
        )
        version = await self._session.scalar(
            select(BusinessObjectVersion).where(
                BusinessObjectVersion.workspace_id == self._workspace_id,
                BusinessObjectVersion.id == UUID(version_id),
            )
        )
        if target is None or version is None or version.version != target.current_version:
            return "conflict", None, None, None
        return "new_version", target.id, version.id, version.version

    async def _verify_expected_versions(self, change_set_id: UUID) -> None:
        operations = tuple(
            (
                await self._session.scalars(
                    select(ImportChangeSetOperation).where(
                        ImportChangeSetOperation.workspace_id == self._workspace_id,
                        ImportChangeSetOperation.change_set_id == change_set_id,
                        ImportChangeSetOperation.operation == "new_version",
                    )
                )
            ).all()
        )
        for operation in operations:
            target = await self._session.scalar(
                select(BusinessObject).where(
                    BusinessObject.workspace_id == self._workspace_id,
                    BusinessObject.id == operation.target_object_id,
                )
            )
            current = await self._session.scalar(
                select(BusinessObjectVersion).where(
                    BusinessObjectVersion.workspace_id == self._workspace_id,
                    BusinessObjectVersion.object_id == operation.target_object_id,
                    BusinessObjectVersion.version == target.current_version if target else False,
                )
            )
            if (
                target is None
                or current is None
                or current.id != operation.expected_version_id
                or current.version != operation.expected_version
            ):
                raise ImportChangeSetConflictError(
                    "Canonical business truth changed after dry-run review; create a new change set"
                )

    async def _require_policy_version(self, version: int | None) -> None:
        if version is None:
            raise ImportChangeSetConflictError("An active policy version is required")
        policy = await self._session.scalar(
            select(Policy.id).where(
                Policy.workspace_id == self._workspace_id,
                Policy.version == version,
                Policy.status == "active",
            ).limit(1)
        )
        if policy is None:
            raise ImportChangeSetConflictError(
                "The reviewed policy version is not active in this workspace"
            )

    async def _job(self, job_id: UUID, *, lock: bool = False) -> ImportJob:
        statement = select(ImportJob).where(
            ImportJob.workspace_id == self._workspace_id, ImportJob.id == job_id
        )
        if lock:
            statement = statement.with_for_update()
        item = await self._session.scalar(statement)
        if item is None:
            raise ImportChangeSetNotFoundError("Import job was not found")
        return item

    async def _current(self, job_id: UUID, *, lock: bool = False) -> ImportChangeSet:
        job = await self._job(job_id)
        if job.selected_change_set_id is None:
            raise ImportChangeSetNotFoundError("Import change set was not found")
        statement = select(ImportChangeSet).where(
            ImportChangeSet.workspace_id == self._workspace_id,
            ImportChangeSet.id == job.selected_change_set_id,
        )
        if lock:
            statement = statement.with_for_update()
        item = await self._session.scalar(statement)
        if item is None:
            raise ImportChangeSetNotFoundError("Import change set was not found")
        return item

    async def _record(self, item: ImportChangeSet) -> ChangeSetRecord:
        pairs = tuple(
            (
                await self._session.execute(
                    select(ImportChangeSetOperation, ImportRow.source_row_number)
                    .join(ImportRow, ImportRow.id == ImportChangeSetOperation.row_id)
                    .where(
                        ImportChangeSetOperation.workspace_id == self._workspace_id,
                        ImportChangeSetOperation.change_set_id == item.id,
                    )
                    .order_by(ImportChangeSetOperation.sequence)
                )
            ).all()
        )
        return ChangeSetRecord(
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
            operations=tuple(
                ChangeSetOperationRecord(
                    id=operation.id,
                    source_row_number=row_number,
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
                for operation, row_number in pairs
            ),
            created_by=item.created_by,
            created_at=item.created_at,
        )

    def _append_lineage(
        self,
        job: ImportJob,
        change_set: ImportChangeSet,
        context: UploadMutationContext,
        action: str,
        event_type: str,
    ) -> None:
        evidence = {
            "jobId": str(job.id),
            "changeSetId": str(change_set.id),
            "changeSetVersion": change_set.version,
            "planHash": change_set.plan_hash,
            "approvalState": change_set.approval_state,
            "policyVersion": change_set.approval_policy_version,
            "compensationPolicyVersion": job.compensation_policy_version,
        }
        self._session.add_all(
            [
                AuditEvent(
                    id=uuid4(), workspace_id=self._workspace_id,
                    actor_type=context.actor_type, actor_id=context.actor_id,
                    session_id=context.session_id, request_id=context.request_id,
                    action=action, resource_type="import_change_set",
                    resource_id=str(change_set.id), outcome="succeeded",
                    reason=change_set.business_purpose, evidence=evidence,
                ),
                OutboxEvent(
                    id=uuid4(), workspace_id=self._workspace_id,
                    aggregate_type="import_change_set", aggregate_id=str(change_set.id),
                    event_type=event_type, event_version=1, payload=evidence,
                ),
            ]
        )


def _hash_plan(job: ImportJob, version: int, plan: list[dict]) -> str:
    encoded = json.dumps(
        {
            "jobId": str(job.id),
            "mappingVersionId": str(job.selected_mapping_version_id),
            "parserVersion": job.parser_version,
            "version": version,
            "operations": plan,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _operation_key(workspace_id: UUID, job_id: UUID, row_id: str, version: int) -> str:
    value = f"{workspace_id}:{job_id}:{row_id}:{version}"
    return f"import-op-{hashlib.sha256(value.encode()).hexdigest()}"


def _summary(plan: list[dict]) -> dict:
    result = {"create": 0, "newVersion": 0, "skip": 0, "conflict": 0, "total": len(plan)}
    for item in plan:
        key = "newVersion" if item["operation"] == "new_version" else item["operation"]
        result[key] += 1
    return result
