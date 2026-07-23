import pytest
from grovello.import_change_sets import ImportApplyInput
from temporalio.exceptions import ActivityError

from grovello_workers.workflows import import_apply as workflow_module
from grovello_workers.workflows.import_apply import (
    ImportApplyWorkflow,
    ImportCompensationWorkflow,
)


def payload() -> ImportApplyInput:
    return ImportApplyInput(
        workspace_id="00000000-0000-4000-8000-000000000001",
        job_id="11111111-1111-4111-8111-111111111111",
        change_set_id="22222222-2222-4222-8222-222222222222",
        actor_type="human",
        actor_id="northstar-owner",
        session_id="owner-session",
        request_id="owner-request",
    )


@pytest.mark.asyncio
async def test_apply_workflow_runs_bounded_idempotent_activity(monkeypatch) -> None:
    calls = []

    async def execute_activity(function, argument, **options):
        calls.append((function.__name__, options["retry_policy"].maximum_attempts))
        return "completed"

    monkeypatch.setattr(workflow_module.workflow, "execute_activity", execute_activity)
    workflow = ImportApplyWorkflow()
    assert await workflow.run(payload()) == "completed"
    assert workflow.status() == "completed"
    assert calls == [("apply_import_change_set", 3)]


@pytest.mark.asyncio
async def test_apply_failure_is_persisted_after_bounded_retries(monkeypatch) -> None:
    calls = []

    async def execute_activity(function, argument, **options):
        calls.append(function.__name__)
        if function.__name__ == "apply_import_change_set":
            raise ActivityError(
                "failed",
                scheduled_event_id=1,
                started_event_id=2,
                identity="test",
                activity_type="apply_import_change_set",
                activity_id="apply",
                retry_state=None,
            )
        return "partially_completed"

    monkeypatch.setattr(workflow_module.workflow, "execute_activity", execute_activity)
    workflow = ImportApplyWorkflow()
    assert await workflow.run(payload()) == "partially_completed"
    assert calls == ["apply_import_change_set", "fail_import_apply"]


@pytest.mark.asyncio
async def test_compensation_has_distinct_durable_workflow(monkeypatch) -> None:
    calls = []

    async def execute_activity(function, argument, **options):
        calls.append(function.__name__)
        return "compensated"

    monkeypatch.setattr(workflow_module.workflow, "execute_activity", execute_activity)
    workflow = ImportCompensationWorkflow()
    assert await workflow.run(payload()) == "compensated"
    assert workflow.status() == "compensated"
    assert calls == ["compensate_import_change_set"]
