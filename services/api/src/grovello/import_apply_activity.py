from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from temporalio import activity
from temporalio.exceptions import ApplicationError

from grovello.business_truth import (
    CitationDraft,
    CreateBusinessObjectCommand,
    CreateBusinessObjectVersionCommand,
    MutationContext,
    SqlAlchemyBusinessTruthStore,
)
from grovello.database import workspace_session
from grovello.import_change_sets import ImportApplyInput
from grovello.models import (
    AuditEvent,
    BusinessObject,
    BusinessObjectVersion,
    BusinessTruthCitation,
    ImportChangeSet,
    ImportChangeSetOperation,
    ImportJob,
    ImportRow,
    OutboxEvent,
)


@activity.defn(name="grovello-apply-import-change-set")
async def apply_import_change_set(payload: ImportApplyInput) -> str:
    workspace_id = UUID(payload.workspace_id)
    change_set_id = UUID(payload.change_set_id)
    operation_ids = await _planned_operation_ids(workspace_id, change_set_id)
    for position, operation_id in enumerate(operation_ids, start=1):
        activity.heartbeat({"operation": position, "total": len(operation_ids)})
        await _apply_operation(workspace_id, operation_id, payload)
    return await _finish_apply(workspace_id, UUID(payload.job_id), change_set_id)


@activity.defn(name="grovello-fail-import-apply")
async def fail_import_apply(payload: ImportApplyInput) -> str:
    workspace_id = UUID(payload.workspace_id)
    job_id = UUID(payload.job_id)
    async with workspace_session(workspace_id) as session:
        job = await session.scalar(
            select(ImportJob)
            .where(ImportJob.workspace_id == workspace_id, ImportJob.id == job_id)
            .with_for_update()
        )
        if job is None:
            raise ApplicationError("Import job was not found", non_retryable=True)
        if job.status in {"completed", "partially_completed", "cancelled"}:
            return job.status
        applied = await session.scalar(
            select(ImportChangeSetOperation)
            .where(
                ImportChangeSetOperation.workspace_id == workspace_id,
                ImportChangeSetOperation.change_set_id == UUID(payload.change_set_id),
                ImportChangeSetOperation.status == "applied",
            )
            .limit(1)
        )
        job.status = "partially_completed" if applied else "failed"
        job.failure_code = "import_apply_failed_after_retries"
        job.failure_detail = "Import apply failed closed after bounded retries"
        _lineage(session, job, "business_truth.import.apply_failed", "BusinessImportApplyFailed")
        return job.status


@activity.defn(name="grovello-compensate-import-change-set")
async def compensate_import_change_set(payload: ImportApplyInput) -> str:
    workspace_id = UUID(payload.workspace_id)
    change_set_id = UUID(payload.change_set_id)
    operation_ids = await _applied_operation_ids(workspace_id, change_set_id)
    for position, operation_id in enumerate(operation_ids, start=1):
        activity.heartbeat({"operation": position, "total": len(operation_ids)})
        await _compensate_operation(workspace_id, operation_id, payload)
    async with workspace_session(workspace_id) as session:
        job = await session.scalar(
            select(ImportJob)
            .where(
                ImportJob.workspace_id == workspace_id,
                ImportJob.id == UUID(payload.job_id),
            )
            .with_for_update()
        )
        if job is None:
            raise ApplicationError("Import job was not found", non_retryable=True)
        job.status = "compensated"
        _lineage(
            session,
            job,
            "business_truth.import.compensated",
            "BusinessImportCompensated",
        )
    return "compensated"


@activity.defn(name="grovello-fail-import-compensation")
async def fail_import_compensation(payload: ImportApplyInput) -> str:
    workspace_id = UUID(payload.workspace_id)
    async with workspace_session(workspace_id) as session:
        job = await session.scalar(
            select(ImportJob)
            .where(
                ImportJob.workspace_id == workspace_id,
                ImportJob.id == UUID(payload.job_id),
            )
            .with_for_update()
        )
        if job is None:
            raise ApplicationError("Import job was not found", non_retryable=True)
        if job.status == "compensated":
            return "compensated"
        job.status = "partially_completed"
        job.failure_code = "import_compensation_blocked"
        job.failure_detail = "Compensation stopped to preserve a concurrent owner edit"
        _lineage(
            session,
            job,
            "business_truth.import.compensation_blocked",
            "BusinessImportCompensationBlocked",
        )
    return "partially_completed"


async def _planned_operation_ids(workspace_id: UUID, change_set_id: UUID) -> tuple[UUID, ...]:
    async with workspace_session(workspace_id) as session:
        return tuple(
            (
                await session.scalars(
                    select(ImportChangeSetOperation.id)
                    .where(
                        ImportChangeSetOperation.workspace_id == workspace_id,
                        ImportChangeSetOperation.change_set_id == change_set_id,
                        ImportChangeSetOperation.status == "planned",
                    )
                    .order_by(ImportChangeSetOperation.sequence)
                )
            ).all()
        )


async def _applied_operation_ids(workspace_id: UUID, change_set_id: UUID) -> tuple[UUID, ...]:
    async with workspace_session(workspace_id) as session:
        return tuple(
            (
                await session.scalars(
                    select(ImportChangeSetOperation.id)
                    .where(
                        ImportChangeSetOperation.workspace_id == workspace_id,
                        ImportChangeSetOperation.change_set_id == change_set_id,
                        ImportChangeSetOperation.status == "applied",
                    )
                    .order_by(ImportChangeSetOperation.sequence.desc())
                )
            ).all()
        )


async def _apply_operation(
    workspace_id: UUID, operation_id: UUID, payload: ImportApplyInput
) -> None:
    async with workspace_session(workspace_id) as session:
        operation = await session.scalar(
            select(ImportChangeSetOperation)
            .where(
                ImportChangeSetOperation.workspace_id == workspace_id,
                ImportChangeSetOperation.id == operation_id,
            )
            .with_for_update()
        )
        if operation is None:
            raise ApplicationError("Import operation was not found", non_retryable=True)
        if operation.status == "applied":
            return
        if operation.status != "planned" or operation.operation not in {"create", "new_version"}:
            raise ApplicationError("Import operation is not applicable", non_retryable=True)
        change_set = await session.scalar(
            select(ImportChangeSet).where(
                ImportChangeSet.workspace_id == workspace_id,
                ImportChangeSet.id == operation.change_set_id,
            )
        )
        row = await session.scalar(
            select(ImportRow).where(
                ImportRow.workspace_id == workspace_id,
                ImportRow.id == operation.row_id,
            )
        )
        job = await session.scalar(
            select(ImportJob).where(
                ImportJob.workspace_id == workspace_id,
                ImportJob.id == change_set.job_id if change_set else False,
            )
        )
        if change_set is None or row is None or job is None or job.status != "applying":
            raise ApplicationError("Import apply state changed", non_retryable=True)
        data = operation.input_snapshot
        citations = tuple(
            CitationDraft(
                evidence_version_id=UUID(item["evidenceVersionId"]),
                claim_text=item["claimText"],
                locator=item.get("locator", {}),
            )
            for item in data.get("citations", [])
        )
        context = MutationContext(
            actor_type=payload.actor_type,
            actor_id=payload.actor_id,
            session_id=payload.session_id,
            request_id=payload.request_id,
            idempotency_key=operation.operation_key,
        )
        store = SqlAlchemyBusinessTruthStore(session, workspace_id)
        if operation.operation == "create":
            result = await store.create_object(
                CreateBusinessObjectCommand(
                    object_type=job.object_type,
                    slug=data["slug"],
                    name=data["name"],
                    status=data["status"],
                    locale=data["locale"],
                    payload=data["payload"],
                    business_purpose=change_set.business_purpose,
                    change_summary=f"Import row {row.source_row_number} created the canonical object",
                    source_type="import",
                    source_ref=f"import-job:{job.id}:row:{row.source_row_number}",
                    input_versions={
                        **job.input_versions,
                        "changeSetId": str(change_set.id),
                        "changeSetVersion": change_set.version,
                        "sourceContentHash": row.content_hash,
                    },
                    citations=citations,
                ),
                context,
            )
            compensation = {"kind": "archive_created"}
        else:
            target = await session.scalar(
                select(BusinessObject)
                .where(
                    BusinessObject.workspace_id == workspace_id,
                    BusinessObject.id == operation.target_object_id,
                )
                .with_for_update()
            )
            current = await session.scalar(
                select(BusinessObjectVersion).where(
                    BusinessObjectVersion.workspace_id == workspace_id,
                    BusinessObjectVersion.id == operation.expected_version_id
                )
            )
            if (
                target is None
                or current is None
                or target.current_version != operation.expected_version
                or current.version != operation.expected_version
            ):
                raise ApplicationError(
                    "Canonical business truth changed after change-set approval", non_retryable=True
                )
            compensation = {
                "kind": "restore_version",
                "versionId": str(current.id),
                "version": current.version,
                "name": current.name,
                "status": current.status,
                "locale": current.locale,
                "payload": current.payload,
                "citations": [
                    {
                        "evidenceVersionId": str(citation.evidence_version_id),
                        "claimText": citation.claim_text,
                        "locator": citation.locator,
                    }
                    for citation in (
                        await session.scalars(
                            select(BusinessTruthCitation).where(
                                BusinessTruthCitation.workspace_id == workspace_id,
                                BusinessTruthCitation.citing_version_id == current.id
                            )
                        )
                    ).all()
                ],
            }
            result = await store.create_version(
                target.id,
                CreateBusinessObjectVersionCommand(
                    name=data["name"], status=data["status"], locale=data["locale"],
                    payload=data["payload"], business_purpose=change_set.business_purpose,
                    change_summary=f"Import row {row.source_row_number} created a new version",
                    source_type="import",
                    source_ref=f"import-job:{job.id}:row:{row.source_row_number}",
                    input_versions={
                        **job.input_versions,
                        "changeSetId": str(change_set.id),
                        "changeSetVersion": change_set.version,
                        "expectedVersionId": str(operation.expected_version_id),
                        "sourceContentHash": row.content_hash,
                    },
                    citations=citations,
                ),
                context,
            )
        operation.status = "applied"
        operation.result_object_id = result.object.id
        operation.result_version_id = result.object.version.id
        operation.result_version = result.object.version.version
        operation.compensation_snapshot = compensation
        operation.applied_at = datetime.now(UTC)
        row.status = "applied"
        row.planned_operation = operation.operation
        row.applied_object_id = result.object.id
        row.applied_version_id = result.object.version.id


async def _finish_apply(workspace_id: UUID, job_id: UUID, change_set_id: UUID) -> str:
    async with workspace_session(workspace_id) as session:
        job = await session.scalar(
            select(ImportJob)
            .where(ImportJob.workspace_id == workspace_id, ImportJob.id == job_id)
            .with_for_update()
        )
        change_set = await session.scalar(
            select(ImportChangeSet)
            .where(
                ImportChangeSet.workspace_id == workspace_id,
                ImportChangeSet.id == change_set_id,
            )
            .with_for_update()
        )
        if job is None or change_set is None:
            raise ApplicationError("Import apply records were not found", non_retryable=True)
        operations = tuple(
            (
                await session.scalars(
                    select(ImportChangeSetOperation).where(
                        ImportChangeSetOperation.workspace_id == workspace_id,
                        ImportChangeSetOperation.change_set_id == change_set_id
                    )
                )
            ).all()
        )
        applied = sum(item.status == "applied" for item in operations)
        failed = sum(item.status == "failed" for item in operations)
        job.applied_rows = applied
        job.completed_at = datetime.now(UTC)
        job.status = "partially_completed" if failed else "completed"
        job.result_summary = {
            **job.result_summary,
            "changeSetId": str(change_set.id),
            "changeSetVersion": change_set.version,
            "planHash": change_set.plan_hash,
            "appliedRows": applied,
            "failedRows": failed,
        }
        change_set.status = "applied"
        _lineage(session, job, "business_truth.import.applied", "BusinessImportApplied")
        return job.status


async def _compensate_operation(
    workspace_id: UUID, operation_id: UUID, payload: ImportApplyInput
) -> None:
    async with workspace_session(workspace_id) as session:
        operation = await session.scalar(
            select(ImportChangeSetOperation)
            .where(
                ImportChangeSetOperation.workspace_id == workspace_id,
                ImportChangeSetOperation.id == operation_id,
            )
            .with_for_update()
        )
        if operation is None or operation.result_object_id is None:
            raise ApplicationError("Applied import operation was not found", non_retryable=True)
        if operation.status == "compensated":
            return
        target = await session.scalar(
            select(BusinessObject)
            .where(
                BusinessObject.workspace_id == workspace_id,
                BusinessObject.id == operation.result_object_id,
            )
            .with_for_update()
        )
        result_version = await session.scalar(
            select(BusinessObjectVersion).where(
                BusinessObjectVersion.workspace_id == workspace_id,
                BusinessObjectVersion.id == operation.result_version_id
            )
        )
        if (
            target is None
            or result_version is None
            or target.current_version != operation.result_version
        ):
            raise ApplicationError(
                "Compensation stopped because the owner created a newer version", non_retryable=True
            )
        snapshot = operation.compensation_snapshot
        if snapshot.get("kind") == "restore_version":
            name = snapshot["name"]
            status = snapshot["status"]
            locale = snapshot["locale"]
            data = snapshot["payload"]
            citations = tuple(
                CitationDraft(
                    evidence_version_id=UUID(item["evidenceVersionId"]),
                    claim_text=item["claimText"],
                    locator=item.get("locator", {}),
                )
                for item in snapshot.get("citations", [])
            )
        else:
            name = result_version.name
            status = "archived"
            locale = result_version.locale
            data = result_version.payload
            citations = ()
        store = SqlAlchemyBusinessTruthStore(session, workspace_id)
        result = await store.create_version(
            target.id,
            CreateBusinessObjectVersionCommand(
                name=name, status=status, locale=locale, payload=data,
                business_purpose="Compensate an approved business-truth import",
                change_summary="Create a compensating version without rewriting import history",
                source_type="import", source_ref=f"import-compensation:{operation.change_set_id}",
                input_versions={
                    "compensatedOperationId": str(operation.id),
                    "compensatedVersionId": str(operation.result_version_id),
                },
                citations=citations,
            ),
            MutationContext(
                actor_type=payload.actor_type, actor_id=payload.actor_id,
                session_id=payload.session_id, request_id=payload.request_id,
                idempotency_key=f"{operation.operation_key}-compensate",
            ),
        )
        operation.status = "compensated"
        operation.compensated_at = datetime.now(UTC)
        row = await session.scalar(
            select(ImportRow).where(
                ImportRow.workspace_id == workspace_id,
                ImportRow.id == operation.row_id,
            )
        )
        if row is not None:
            row.status = "compensated"
            row.applied_version_id = result.object.version.id


def _lineage(session, job: ImportJob, action: str, event_type: str) -> None:
    evidence = {
        "jobId": str(job.id),
        "status": job.status,
        "changeSetId": str(job.selected_change_set_id),
        "appliedRows": job.applied_rows,
        "failureCode": job.failure_code,
        "compensationPolicyVersion": job.compensation_policy_version,
        "compensationBusinessPurpose": job.compensation_business_purpose,
    }
    session.add_all(
        [
            AuditEvent(
                id=uuid4(), workspace_id=job.workspace_id, actor_type="system",
                actor_id="import-apply-worker", action=action, resource_type="import_job",
                resource_id=str(job.id), outcome="failed" if job.failure_code else "succeeded",
                reason=job.failure_detail, evidence=evidence,
            ),
            OutboxEvent(
                id=uuid4(), workspace_id=job.workspace_id, aggregate_type="import_job",
                aggregate_id=str(job.id), event_type=event_type, event_version=1, payload=evidence,
            ),
        ]
    )
