import pytest
from grovello.asset_uploads import AssetVerificationInput

from grovello_workers.workflows import asset_upload_verification as workflow_module
from grovello_workers.workflows.asset_upload_verification import AssetUploadVerificationWorkflow


@pytest.mark.asyncio
async def test_cancel_before_execution_never_runs_verification() -> None:
    workflow = AssetUploadVerificationWorkflow()
    await workflow.cancel()
    result = await workflow.run(
        AssetVerificationInput(
            workspace_id="00000000-0000-4000-8000-000000000001",
            upload_session_id="11111111-1111-4111-8111-111111111111",
            object_key="workspaces/one/staging/session/object",
            expected_content_type="application/pdf",
            expected_content_length=128,
            expected_sha256="a" * 64,
        )
    )
    assert result == "cancelled"
    assert workflow.status() == "cancelled"


@pytest.mark.asyncio
async def test_workflow_verifies_then_scans_with_bounded_retries(monkeypatch) -> None:
    calls = []

    async def execute_activity(activity, payload, **options):
        calls.append((activity.__name__, options["retry_policy"].maximum_attempts))
        return "scan_pending" if len(calls) == 1 else "ready_to_finalize"

    monkeypatch.setattr(workflow_module.workflow, "execute_activity", execute_activity)
    workflow = AssetUploadVerificationWorkflow()
    result = await workflow.run(
        AssetVerificationInput(
            workspace_id="00000000-0000-4000-8000-000000000001",
            upload_session_id="11111111-1111-4111-8111-111111111111",
            object_key="workspaces/one/staging/session/object",
            expected_content_type="application/pdf",
            expected_content_length=128,
            expected_sha256="a" * 64,
        )
    )
    assert result == "ready_to_finalize"
    assert calls == [("verify_asset_upload", 5), ("scan_asset_upload", 3)]
