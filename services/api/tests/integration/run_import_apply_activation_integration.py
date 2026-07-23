"""Run with a PostgreSQL-backed API environment; exits non-zero on contract failure."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import delete, select, update
from temporalio.testing import ActivityEnvironment

from grovello.asset_uploads import UploadMutationContext
from grovello.database import workspace_session
from grovello.import_apply_activity import (
    apply_import_change_set,
    compensate_import_change_set,
)
from grovello.import_change_sets import (
    ApprovalDecisionCommand,
    CreateChangeSetCommand,
    ImportApplyInput,
    SqlAlchemyImportChangeSetStore,
    StartCompensationCommand,
)
from grovello.models import (
    BusinessObject,
    ImportJob,
    ImportRow,
    Organization,
    Policy,
    User,
    Workspace,
    WorkspaceMembership,
)
from grovello.workspace_onboarding import (
    ActivateWorkspaceOnboardingCommand,
    CreateWorkspaceOnboardingCommand,
    OnboardingMutationContext,
    SqlAlchemyWorkspaceOnboardingStore,
    WorkspaceOnboardingConflictError,
)


async def main() -> None:
    organization_id = uuid4()
    workspace_id = uuid4()
    user_id = uuid4()
    membership_id = uuid4()
    job_id = uuid4()
    row_id = uuid4()
    suffix = workspace_id.hex[:10]
    now = datetime.now(UTC)

    async with workspace_session(workspace_id) as session:
        session.add_all(
            [
                Organization(id=organization_id, slug=f"p2d3-{suffix}", name="P2-D3 Integration"),
                Workspace(
                    id=workspace_id,
                    organization_id=organization_id,
                    slug=f"p2d3-{suffix}",
                    name="P2-D3 Integration",
                    default_locale="en",
                    timezone="UTC",
                    currency="USD",
                ),
                User(
                    id=user_id,
                    organization_id=organization_id,
                    external_subject=f"p2d3-{suffix}",
                    email=f"p2d3-{suffix}@example.invalid",
                    display_name="P2-D3 Integration Owner",
                    status="active",
                ),
            ]
        )
        await session.flush()
        session.add_all(
            [
                WorkspaceMembership(
                    id=membership_id,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    status="active",
                ),
                Policy(
                    id=uuid4(),
                    workspace_id=workspace_id,
                    key="business-profile-baseline",
                    version=1,
                    status="active",
                    rules={"activeImportRequiresApproval": True},
                ),
                ImportJob(
                    id=job_id,
                    workspace_id=workspace_id,
                    actor_id="integration-owner",
                    session_id="integration-session",
                    request_id="integration-request",
                    idempotency_key=f"job-{suffix}",
                    business_purpose="Verify governed import apply and activation",
                    object_type="product",
                    source_format="csv",
                    schema_version=1,
                    locale="en",
                    status="ready_for_review",
                    total_rows=1,
                    valid_rows=1,
                    invalid_rows=0,
                    applied_rows=0,
                    parser_version="grovello-import-parser-v1",
                    input_versions={"sourceChecksum": "a" * 64},
                    result_summary={},
                    retention_deadline=now + timedelta(days=1),
                ),
            ]
        )
        await session.flush()
        session.add(
            ImportRow(
                id=row_id,
                workspace_id=workspace_id,
                job_id=job_id,
                source_row_number=1,
                content_hash="b" * 64,
                normalized_data={
                    "slug": f"integration-product-{suffix}",
                    "name": "Integration Product",
                    "status": "active",
                    "locale": "en",
                    "payload": {"sku": f"INT-{suffix.upper()}"},
                    "citations": [],
                },
                target_identity={"matchKind": "new"},
                status="valid",
            )
        )

    try:
        async with workspace_session(workspace_id) as session:
            onboarding = SqlAlchemyWorkspaceOnboardingStore(session, workspace_id)
            await onboarding.create(
                CreateWorkspaceOnboardingCommand(
                    business_purpose="Verify exact business profile activation",
                    required_object_types=("product",),
                    input_versions={"importJobId": str(job_id)},
                ),
                OnboardingMutationContext(
                    actor_type="human",
                    actor_id="integration-owner",
                    session_id="integration-session",
                    request_id="onboarding-request",
                    idempotency_key=f"onboarding-{suffix}",
                ),
            )
            try:
                await onboarding.activate(
                    ActivateWorkspaceOnboardingCommand(
                        business_purpose="Reject an incomplete integration profile",
                        policy_version=1,
                        reviewed_warning_codes=(),
                    ),
                    OnboardingMutationContext(
                        actor_type="human",
                        actor_id="integration-owner",
                        session_id="integration-session",
                        request_id="blocked-activation-request",
                        idempotency_key=f"blocked-activate-{suffix}",
                    ),
                )
            except WorkspaceOnboardingConflictError:
                pass
            else:
                raise AssertionError("Incomplete profile activation must be blocked")

        async with workspace_session(workspace_id) as session:
            blocked = await SqlAlchemyWorkspaceOnboardingStore(session, workspace_id).get()
            assert blocked.status == "blocked"
            assert blocked.validation_gaps[0]["code"] == "missing_active_product"

        mutation = UploadMutationContext(
            actor_type="human",
            actor_id="integration-owner",
            session_id="integration-session",
            request_id="integration-request",
            idempotency_key=f"plan-{suffix}",
        )
        async with workspace_session(workspace_id) as session:
            store = SqlAlchemyImportChangeSetStore(session, workspace_id)
            planned = await store.create(
                job_id,
                CreateChangeSetCommand(
                    business_purpose="Apply an approved integration product",
                    policy_version=1,
                ),
                mutation,
            )
            assert planned.change_set.approval_state == "pending"
            await store.decide(
                job_id,
                ApprovalDecisionCommand(
                    decision="approved",
                    reason="Approve the exact active integration product plan",
                    policy_version=1,
                ),
                UploadMutationContext(
                    actor_type="human",
                    actor_id="integration-approver",
                    session_id="approver-session",
                    request_id="approval-request",
                    idempotency_key=f"approve-{suffix}",
                ),
            )
            started = await store.start_apply(
                job_id,
                UploadMutationContext(
                    actor_type="human",
                    actor_id="integration-owner",
                    session_id="integration-session",
                    request_id="apply-request",
                    idempotency_key=f"apply-{suffix}",
                ),
            )
            change_set_id = started.change_set.id

        payload = ImportApplyInput(
            workspace_id=str(workspace_id),
            job_id=str(job_id),
            change_set_id=str(change_set_id),
            actor_type="human",
            actor_id="integration-owner",
            session_id="integration-session",
            request_id="apply-request",
        )
        activity_environment = ActivityEnvironment()
        assert await activity_environment.run(apply_import_change_set, payload) == "completed"

        async with workspace_session(workspace_id) as session:
            onboarding = SqlAlchemyWorkspaceOnboardingStore(session, workspace_id)
            activated = await onboarding.activate(
                ActivateWorkspaceOnboardingCommand(
                    business_purpose="Activate the exact approved integration profile",
                    policy_version=1,
                    reviewed_warning_codes=(),
                ),
                OnboardingMutationContext(
                    actor_type="human",
                    actor_id="integration-owner",
                    session_id="integration-session",
                    request_id="activation-request",
                    idempotency_key=f"activate-{suffix}",
                ),
            )
            assert activated.onboarding.status == "active"
            assert len(activated.onboarding.activation_snapshot["objectVersions"]) == 1

        async with workspace_session(workspace_id) as session:
            store = SqlAlchemyImportChangeSetStore(session, workspace_id)
            compensated = await store.start_compensation(
                job_id,
                StartCompensationCommand(
                    business_purpose="Compensate the accepted integration import",
                    policy_version=1,
                ),
                UploadMutationContext(
                    actor_type="human",
                    actor_id="integration-owner",
                    session_id="integration-session",
                    request_id="compensation-request",
                    idempotency_key=f"compensate-{suffix}",
                ),
            )
            assert compensated.workflow_id.startswith("grovello-import-compensate-")
        assert await activity_environment.run(compensate_import_change_set, payload) == "compensated"

        async with workspace_session(workspace_id) as session:
            product = await session.scalar(
                select(BusinessObject).where(
                    BusinessObject.workspace_id == workspace_id,
                    BusinessObject.object_type == "product",
                )
            )
            job = await session.scalar(
                select(ImportJob).where(
                    ImportJob.workspace_id == workspace_id,
                    ImportJob.id == job_id,
                )
            )
            assert product is not None
            assert product.status == "archived", (
                product.status,
                product.current_version,
            )
            assert product.current_version == 2
            assert job is not None and job.status == "compensated"
    finally:
        async with workspace_session(workspace_id) as session:
            await session.execute(
                update(ImportJob)
                .where(ImportJob.workspace_id == workspace_id, ImportJob.id == job_id)
                .values(selected_change_set_id=None)
            )
            await session.execute(delete(Organization).where(Organization.id == organization_id))


if __name__ == "__main__":
    asyncio.run(main())
