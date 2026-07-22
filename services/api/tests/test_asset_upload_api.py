from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from grovello.access import (
    NORTHSTAR_WORKSPACE_ID,
    WORKSPACES,
    ActorContext,
    AuthorizedWorkspace,
    WorkspaceGrant,
)
from grovello.api.dependencies import (
    get_asset_finalization_launcher,
    get_asset_finalization_store,
    get_asset_upload_store,
    get_asset_verification_launcher,
    require_workspace_access,
)
from grovello.asset_finalization import AssetFinalizationInput, AssetFinalizationRequestResult
from grovello.asset_uploads import (
    AssetUploadRecord,
    AssetVerificationInput,
    CreateUploadResult,
    UploadMutationResult,
)
from grovello.main import app
from grovello.object_storage import UploadGrant, UploadGrantMethod

SHA256 = "a" * 64


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


def record(state: str = "initiated", workflow_id: str | None = None) -> AssetUploadRecord:
    now = datetime.now(UTC)
    return AssetUploadRecord(
        id=UUID("11111111-1111-4111-8111-111111111111"),
        workspace_id=NORTHSTAR_WORKSPACE_ID,
        target_asset_id=None,
        actor_id="northstar-owner",
        business_purpose="Publish an approved product datasheet",
        state=state,
        original_filename="controller.pdf",
        declared_mime_type="application/pdf",
        declared_size=128,
        declared_sha256=SHA256,
        expires_at=now + timedelta(minutes=30),
        completed_at=now if workflow_id else None,
        cancelled_at=now if state == "cancelled" else None,
        workflow_id=workflow_id,
        failure_code=None,
        failure_detail=None,
        verified_size=128 if state == "scanning" else None,
        verified_sha256=SHA256 if state == "scanning" else None,
        verified_mime_type="application/pdf" if state == "scanning" else None,
        verified_at=now if state == "scanning" else None,
        scan_status="pending" if state == "scanning" else "not_started",
        scan_provider=None,
        scan_reference=None,
        scan_attempts=0,
        scanned_at=None,
        quarantine_object_key=None,
        quarantined_at=None,
        finalization_workflow_id=None,
        finalized_blob_id=None,
        finalized_asset_id=None,
        finalized_asset_version_id=None,
        finalized_at=None,
        staging_cleanup_status="not_started",
        staging_cleanup_at=None,
        created_at=now,
        updated_at=now,
    )


class FakeStore:
    source = "live"

    def __init__(self) -> None:
        self.item = record()

    async def create(self, command, context) -> CreateUploadResult:
        return CreateUploadResult(
            self.item,
            UploadGrant(
                UploadGrantMethod.POST,
                "http://localhost:9000/grovello",
                datetime.now(UTC) + timedelta(minutes=30),
                fields={
                    "key": f"workspaces/{NORTHSTAR_WORKSPACE_ID}/staging/session/object",
                    "Content-Type": command.content_type,
                    "x-amz-meta-sha256": command.checksum_sha256,
                    "policy": "signed-policy",
                },
            ),
            False,
        )

    async def get(self, upload_session_id) -> AssetUploadRecord:
        return self.item

    async def complete(self, upload_session_id, context):
        workflow_id = f"grovello-asset-verify-{NORTHSTAR_WORKSPACE_ID}-{self.item.id}"
        self.item = record("uploaded", workflow_id)
        verification = AssetVerificationInput(
            str(NORTHSTAR_WORKSPACE_ID), str(self.item.id),
            f"workspaces/{NORTHSTAR_WORKSPACE_ID}/staging/session/object",
            "application/pdf", 128, SHA256,
        )
        return UploadMutationResult(self.item, False), verification

    async def cancel(self, upload_session_id, context) -> UploadMutationResult:
        self.item = record("cancelled", self.item.workflow_id)
        return UploadMutationResult(self.item, False)

    async def commit(self) -> None:
        return None


class FakeLauncher:
    def __init__(self) -> None:
        self.started: list[tuple[str, AssetVerificationInput]] = []
        self.cancelled: list[str] = []

    async def start(self, workflow_id: str, payload: AssetVerificationInput) -> None:
        self.started.append((workflow_id, payload))

    async def cancel(self, workflow_id: str) -> None:
        self.cancelled.append(workflow_id)


@pytest.fixture
def asset_client() -> Iterator[tuple[TestClient, FakeStore, FakeLauncher]]:
    store = FakeStore()
    launcher = FakeLauncher()
    app.dependency_overrides[get_asset_upload_store] = lambda: store
    app.dependency_overrides[get_asset_verification_launcher] = lambda: launcher
    try:
        with TestClient(app) as client:
            yield client, store, launcher
    finally:
        app.dependency_overrides.pop(get_asset_upload_store, None)
        app.dependency_overrides.pop(get_asset_verification_launcher, None)


def payload() -> dict:
    return {
        "originalFilename": "controller.pdf",
        "contentType": "application/pdf",
        "contentLength": 128,
        "checksumSha256": SHA256,
        "businessPurpose": "Publish an approved product datasheet",
    }


def test_create_upload_returns_a_restricted_post_contract(asset_client) -> None:
    client, _store, _launcher = asset_client
    response = client.post(
        "/api/v1/assets/upload-sessions",
        headers=headers("northstar-owner", "create-upload"),
        json=payload(),
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["upload"]["method"] == "POST"
    assert data["upload"]["fields"]["Content-Type"] == "application/pdf"
    assert data["upload"]["fields"]["x-amz-meta-sha256"] == SHA256
    assert data["session"]["state"] == "initiated"


def test_complete_starts_temporal_and_does_not_claim_a_ready_asset(asset_client) -> None:
    client, store, launcher = asset_client
    response = client.post(
        f"/api/v1/assets/upload-sessions/{store.item.id}/complete",
        headers=headers("northstar-owner", "complete-upload"),
    )

    assert response.status_code == 202
    assert response.json()["data"]["session"]["state"] == "uploaded"
    assert response.json()["data"]["session"]["scanStatus"] == "not_started"
    assert len(launcher.started) == 1
    assert launcher.started[0][0].startswith("grovello-asset-verify-")
    assert "asset" not in response.json()["data"]


def test_scanning_status_is_explicitly_pending(asset_client) -> None:
    client, store, _launcher = asset_client
    store.item = record("scanning", f"workflow-{uuid4()}")
    response = client.get(
        f"/api/v1/assets/upload-sessions/{store.item.id}",
        headers=headers("northstar-analyst"),
    )
    assert response.status_code == 200
    assert response.json()["data"]["state"] == "scanning"
    assert response.json()["data"]["scanStatus"] == "pending"


def test_upload_write_is_forbidden_to_read_only_actor(asset_client) -> None:
    client, _store, _launcher = asset_client
    response = client.post(
        "/api/v1/assets/upload-sessions",
        headers=headers("northstar-analyst", "denied-upload"),
        json=payload(),
    )
    assert response.status_code == 403


def test_cancel_signals_an_existing_verification_workflow(asset_client) -> None:
    client, store, launcher = asset_client
    store.item = record("uploaded", "grovello-asset-verify-existing")
    response = client.post(
        f"/api/v1/assets/upload-sessions/{store.item.id}/cancel",
        headers=headers("northstar-owner", "cancel-upload"),
    )
    assert response.status_code == 200
    assert response.json()["data"]["session"]["state"] == "cancelled"
    assert launcher.cancelled == ["grovello-asset-verify-existing"]


def test_clean_upload_finalization_is_queued_and_does_not_claim_completion() -> None:
    base = record("ready_to_finalize", "grovello-asset-verify-clean")
    finalizing = replace(
        base,
        state="finalizing",
        scan_status="clean",
        scan_provider="clamav",
        scanned_at=datetime.now(UTC),
        verified_size=128,
        verified_sha256=SHA256,
        verified_mime_type="application/pdf",
        verified_at=datetime.now(UTC),
        finalization_workflow_id="grovello-asset-finalize-test",
        staging_cleanup_status="pending",
    )
    workflow_payload = AssetFinalizationInput(
        workspace_id=str(NORTHSTAR_WORKSPACE_ID),
        upload_session_id=str(finalizing.id),
        request_hash="b" * 64,
        object_key="workspaces/one/staging/session/object",
        expected_provider_version_id="version-1",
        expected_content_type="application/pdf",
        expected_content_length=128,
        expected_sha256=SHA256,
        asset_id=str(uuid4()),
        asset_version_id=str(uuid4()),
        blob_id=str(uuid4()),
        destination_object_key="workspaces/one/assets/object",
        name="Controller datasheet",
        slug="controller-datasheet",
        locale="en",
        status="draft",
        metadata={},
        business_purpose="Publish an approved product datasheet",
        change_summary="Finalize the verified original file",
        actor_type="human",
        actor_id="northstar-owner",
        session_id="session-northstar-owner",
        request_id="request-northstar-owner",
    )

    class Store:
        async def request(self, upload_session_id, command, context):
            return AssetFinalizationRequestResult(
                finalizing,
                "grovello-asset-finalize-test",
                workflow_payload,
                False,
            )

        async def commit(self) -> None:
            return None

    class Launcher:
        def __init__(self) -> None:
            self.started = []

        async def start(self, workflow_id, payload) -> None:
            self.started.append((workflow_id, payload))

    launcher = Launcher()
    app.dependency_overrides[get_asset_finalization_store] = lambda: Store()
    app.dependency_overrides[get_asset_finalization_launcher] = lambda: launcher
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/assets/upload-sessions/{finalizing.id}/finalize",
                headers=headers("northstar-owner", "finalize-upload"),
                json={
                    "name": "Controller datasheet",
                    "slug": "controller-datasheet",
                    "locale": "en",
                    "status": "draft",
                    "metadata": {"audience": "engineers"},
                    "changeSummary": "Finalize the verified original file",
                },
            )
    finally:
        app.dependency_overrides.pop(get_asset_finalization_store, None)
        app.dependency_overrides.pop(get_asset_finalization_launcher, None)
    assert response.status_code == 202
    assert response.json()["data"]["session"]["state"] == "finalizing"
    assert response.json()["data"]["session"]["finalizedBlobId"] is None
    assert launcher.started == [("grovello-asset-finalize-test", workflow_payload)]


def test_active_finalization_requires_asset_approval_permission() -> None:
    restricted = AuthorizedWorkspace(
        actor=ActorContext("asset-writer", "asset-writer-session"),
        workspace=WORKSPACES[0],
        grant=WorkspaceGrant(
            workspace_id=NORTHSTAR_WORKSPACE_ID,
            roles=("asset_writer",),
            permissions=frozenset({"asset.write"}),
        ),
    )
    app.dependency_overrides[require_workspace_access] = lambda: restricted
    app.dependency_overrides[get_asset_finalization_store] = lambda: object()
    app.dependency_overrides[get_asset_finalization_launcher] = lambda: object()
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/assets/upload-sessions/{uuid4()}/finalize",
                headers=headers("northstar-owner", "active-finalize"),
                json={
                    "name": "Approved datasheet",
                    "slug": "approved-datasheet",
                    "status": "active",
                    "metadata": {},
                    "changeSummary": "Approve the verified original file",
                },
            )
    finally:
        app.dependency_overrides.pop(require_workspace_access, None)
        app.dependency_overrides.pop(get_asset_finalization_store, None)
        app.dependency_overrides.pop(get_asset_finalization_launcher, None)
    assert response.status_code == 403
    assert response.json()["detail"] == "Permission required: asset.approve"
