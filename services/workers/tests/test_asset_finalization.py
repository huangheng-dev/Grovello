import pytest
from grovello.asset_finalization import AssetFinalizationInput
from grovello.asset_finalization_activity import PromotedAsset
from temporalio.exceptions import ActivityError

from grovello_workers.workflows import asset_finalization as workflow_module
from grovello_workers.workflows.asset_finalization import AssetFinalizationWorkflow


def payload() -> AssetFinalizationInput:
    return AssetFinalizationInput(
        workspace_id="00000000-0000-4000-8000-000000000001",
        upload_session_id="11111111-1111-4111-8111-111111111111",
        request_hash="b" * 64,
        object_key="workspaces/one/staging/session/object",
        expected_provider_version_id="staging-version",
        expected_content_type="application/pdf",
        expected_content_length=128,
        expected_sha256="a" * 64,
        asset_id="22222222-2222-4222-8222-222222222222",
        asset_version_id="33333333-3333-4333-8333-333333333333",
        blob_id="44444444-4444-4444-8444-444444444444",
        destination_object_key="workspaces/one/assets/object",
        name="Controller datasheet",
        slug="controller-datasheet",
        locale="en",
        status="active",
        metadata={},
        business_purpose="Publish an approved product datasheet",
        change_summary="Finalize the verified original file",
        actor_type="human",
        actor_id="northstar-owner",
        session_id="owner-session",
        request_id="owner-request",
    )


def promoted() -> PromotedAsset:
    return PromotedAsset(
        object_key="workspaces/one/assets/object",
        provider_version_id="immutable-version",
        etag="etag",
        byte_size=128,
        content_type="application/pdf",
        sha256="a" * 64,
    )


@pytest.mark.asyncio
async def test_finalization_saga_promotes_commits_then_cleans_staging(monkeypatch) -> None:
    calls = []

    async def execute_activity(function, argument, **options):
        calls.append((function.__name__, options["retry_policy"].maximum_attempts))
        if function.__name__ == "promote_asset_upload":
            return promoted()
        return "finalized"

    monkeypatch.setattr(workflow_module.workflow, "execute_activity", execute_activity)
    workflow = AssetFinalizationWorkflow()
    assert await workflow.run(payload()) == "finalized"
    assert calls == [
        ("promote_asset_upload", 5),
        ("commit_asset_finalization", 5),
        ("cleanup_finalized_asset_staging", 10),
    ]


@pytest.mark.asyncio
async def test_commit_failure_runs_guarded_compensation(monkeypatch) -> None:
    calls = []

    async def execute_activity(function, argument, **options):
        calls.append(function.__name__)
        if function.__name__ == "promote_asset_upload":
            return promoted()
        if function.__name__ == "commit_asset_finalization":
            raise ActivityError(
                "commit failed",
                scheduled_event_id=1,
                started_event_id=2,
                identity="test",
                activity_type="commit_asset_finalization",
                activity_id="commit",
                retry_state=None,
            )
        return "failed"

    monkeypatch.setattr(workflow_module.workflow, "execute_activity", execute_activity)
    workflow = AssetFinalizationWorkflow()
    assert await workflow.run(payload()) == "failed"
    assert calls == [
        "promote_asset_upload",
        "commit_asset_finalization",
        "compensate_asset_promotion",
    ]
