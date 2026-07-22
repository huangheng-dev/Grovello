import pytest
from grovello.business_imports import ImportValidationInput
from temporalio.exceptions import ActivityError

from grovello_workers.workflows import import_validation as workflow_module
from grovello_workers.workflows.import_validation import ImportValidationWorkflow


def payload() -> ImportValidationInput:
    return ImportValidationInput(
        workspace_id="00000000-0000-4000-8000-000000000001",
        job_id="11111111-1111-4111-8111-111111111111",
        mapping_version_id="22222222-2222-4222-8222-222222222222",
    )


@pytest.mark.asyncio
async def test_import_validation_runs_outside_http_with_bounded_retries(monkeypatch) -> None:
    calls = []

    async def execute_activity(function, argument, **options):
        calls.append((function.__name__, options["retry_policy"].maximum_attempts))
        return "ready_for_review"

    monkeypatch.setattr(workflow_module.workflow, "execute_activity", execute_activity)
    workflow = ImportValidationWorkflow()
    assert await workflow.run(payload()) == "ready_for_review"
    assert workflow.status() == "ready_for_review"
    assert calls == [("validate_import", 3)]


@pytest.mark.asyncio
async def test_import_validation_failure_records_terminal_state(monkeypatch) -> None:
    calls = []

    async def execute_activity(function, argument, **options):
        calls.append(function.__name__)
        if function.__name__ == "validate_import":
            raise ActivityError(
                "failed",
                scheduled_event_id=1,
                started_event_id=2,
                identity="test",
                activity_type="validate_import",
                activity_id="validate",
                retry_state=None,
            )
        return "failed"

    monkeypatch.setattr(workflow_module.workflow, "execute_activity", execute_activity)
    workflow = ImportValidationWorkflow()
    assert await workflow.run(payload()) == "failed"
    assert calls == ["validate_import", "fail_import_validation"]
