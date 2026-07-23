from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from grovello.access import NORTHSTAR_WORKSPACE_ID
from grovello.api.dependencies import get_import_apply_launcher, get_import_change_set_store
from grovello.import_change_sets import (
    ChangeSetMutationResult,
    ChangeSetOperationRecord,
    ChangeSetRecord,
    ImportWorkflowStartResult,
)
from grovello.main import app

JOB_ID = UUID("11111111-1111-4111-8111-111111111111")
CHANGE_SET_ID = UUID("22222222-2222-4222-8222-222222222222")
OPERATION_ID = UUID("33333333-3333-4333-8333-333333333333")


def headers(subject: str, key: str | None = None) -> dict[str, str]:
    result = {
        "X-Grovello-Dev-Subject": subject,
        "X-Grovello-Dev-Session": f"session-{subject}",
        "X-Request-ID": f"request-{subject}",
        "X-Workspace-ID": str(NORTHSTAR_WORKSPACE_ID),
    }
    if key:
        result["Idempotency-Key"] = key
    return result


def record(approval_state: str = "pending", status: str = "ready_for_review") -> ChangeSetRecord:
    now = datetime.now(UTC)
    return ChangeSetRecord(
        id=CHANGE_SET_ID,
        job_id=JOB_ID,
        version=1,
        plan_hash="a" * 64,
        status=status,
        approval_state=approval_state,
        approval_policy_version=1,
        approval_requested_by="northstar-owner",
        approval_requested_at=now,
        approval_decided_by=None,
        approval_decided_at=None,
        approval_reason=None,
        business_purpose="Apply the reviewed product catalog",
        summary={"create": 1, "newVersion": 0, "skip": 0, "conflict": 0, "total": 1},
        operations=(
            ChangeSetOperationRecord(
                id=OPERATION_ID,
                source_row_number=1,
                operation="create",
                status="planned",
                target_object_id=None,
                expected_version_id=None,
                expected_version=None,
                result_object_id=None,
                result_version_id=None,
                result_version=None,
                failure_code=None,
            ),
        ),
        created_by="northstar-owner",
        created_at=now,
    )


class FakeChangeSetStore:
    def __init__(self) -> None:
        self.item = record()
        self.commits = 0

    async def create(self, job_id, command, context):
        return ChangeSetMutationResult(self.item, False)

    async def get(self, job_id):
        return self.item

    async def decide(self, job_id, command, context):
        self.item = record(command.decision, "approved" if command.decision == "approved" else "rejected")
        return ChangeSetMutationResult(self.item, False)

    async def start_apply(self, job_id, context):
        return ImportWorkflowStartResult(self.item, f"grovello-import-apply-{job_id}", False)

    async def start_compensation(self, job_id, command, context):
        return ImportWorkflowStartResult(
            self.item, f"grovello-import-compensate-{job_id}", False
        )

    async def commit(self):
        self.commits += 1


class FakeLauncher:
    def __init__(self) -> None:
        self.started = []

    async def start(self, workflow_id, payload):
        self.started.append((workflow_id, payload))

    async def cancel(self, workflow_id):
        return None


@pytest.fixture
def change_set_client() -> Iterator[tuple[TestClient, FakeChangeSetStore, FakeLauncher]]:
    store = FakeChangeSetStore()
    launcher = FakeLauncher()
    app.dependency_overrides[get_import_change_set_store] = lambda: store
    app.dependency_overrides[get_import_apply_launcher] = lambda: launcher
    try:
        with TestClient(app) as client:
            yield client, store, launcher
    finally:
        app.dependency_overrides.pop(get_import_change_set_store, None)
        app.dependency_overrides.pop(get_import_apply_launcher, None)


def test_change_set_review_is_readable_but_mutation_is_permission_gated(change_set_client) -> None:
    client, _store, _launcher = change_set_client
    readable = client.get(
        f"/api/v1/import-jobs/{JOB_ID}/change-set",
        headers=headers("northstar-analyst"),
    )
    denied = client.post(
        f"/api/v1/import-jobs/{JOB_ID}/change-set",
        headers=headers("northstar-analyst", "denied-plan"),
        json={"businessPurpose": "Plan the reviewed product import", "policyVersion": 1},
    )
    assert readable.status_code == 200
    assert readable.json()["data"]["operations"][0]["operation"] == "create"
    assert denied.status_code == 403


def test_approval_handoff_and_apply_launch_are_explicit(change_set_client) -> None:
    client, store, launcher = change_set_client
    approval = client.post(
        f"/api/v1/import-jobs/{JOB_ID}/change-set/approval",
        headers=headers("northstar-owner", "approve-plan"),
        json={
            "decision": "approved",
            "reason": "Reviewed active-version risk and approved the exact plan",
            "policyVersion": 1,
        },
    )
    apply = client.post(
        f"/api/v1/import-jobs/{JOB_ID}/apply",
        headers=headers("northstar-owner", "apply-plan"),
    )
    assert approval.status_code == 200
    assert approval.json()["data"]["changeSet"]["approvalState"] == "approved"
    assert apply.status_code == 202
    assert apply.json()["data"]["workflowId"].startswith("grovello-import-apply-")
    assert store.commits == 1
    assert launcher.started[0][1].change_set_id == str(CHANGE_SET_ID)


def test_compensation_requires_high_risk_permission(change_set_client) -> None:
    client, _store, launcher = change_set_client
    denied = client.post(
        f"/api/v1/import-jobs/{JOB_ID}/compensate",
        headers=headers("northstar-analyst", "denied-compensate"),
        json={
            "businessPurpose": "Compensate the accepted import safely",
            "policyVersion": 1,
        },
    )
    accepted = client.post(
        f"/api/v1/import-jobs/{JOB_ID}/compensate",
        headers=headers("northstar-owner", "compensate-plan"),
        json={
            "businessPurpose": "Compensate the accepted import safely",
            "policyVersion": 1,
        },
    )
    assert denied.status_code == 403
    assert accepted.status_code == 202
    assert launcher.started[-1][0].startswith("grovello-import-compensate-")
