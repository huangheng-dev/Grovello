import pytest
from grovello.business_imports import ImportSourceVerificationInput

from grovello_workers.workflows import import_source_verification as workflow_module
from grovello_workers.workflows.import_source_verification import ImportSourceVerificationWorkflow


def payload() -> ImportSourceVerificationInput:
    return ImportSourceVerificationInput(
        workspace_id="00000000-0000-4000-8000-000000000001",
        job_id="11111111-1111-4111-8111-111111111111",
        source_id="22222222-2222-4222-8222-222222222222",
        object_key="workspaces/one/imports/job/sources/source",
        expected_content_type="text/csv",
        expected_content_length=128,
        expected_sha256="a" * 64,
    )


@pytest.mark.asyncio
async def test_import_workflow_verifies_then_scans_with_bounded_retries(monkeypatch) -> None:
    calls = []

    async def execute_activity(activity, activity_payload, **options):
        calls.append((activity.__name__, options["retry_policy"].maximum_attempts))
        return "scan_pending" if len(calls) == 1 else "ready_for_mapping"

    monkeypatch.setattr(workflow_module.workflow, "execute_activity", execute_activity)
    workflow = ImportSourceVerificationWorkflow()
    result = await workflow.run(payload())
    assert result == "ready_for_mapping"
    assert workflow.status() == "ready_for_mapping"
    assert calls == [("verify_import_source", 5), ("scan_import_source", 3)]


@pytest.mark.asyncio
async def test_import_workflow_stops_before_mapping_when_verification_is_cancelled(monkeypatch) -> None:
    calls = []

    async def execute_activity(activity, activity_payload, **options):
        calls.append(activity.__name__)
        return "cancelled"

    monkeypatch.setattr(workflow_module.workflow, "execute_activity", execute_activity)
    workflow = ImportSourceVerificationWorkflow()
    result = await workflow.run(payload())
    assert result == "cancelled"
    assert calls == ["verify_import_source"]
