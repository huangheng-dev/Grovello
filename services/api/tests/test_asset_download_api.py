from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from grovello.access import NORTHSTAR_WORKSPACE_ID
from grovello.api.dependencies import get_asset_download_store
from grovello.asset_downloads import AssetDownloadResult
from grovello.main import app
from grovello.object_storage import DownloadGrant


def test_active_clean_asset_gets_a_bounded_private_download_grant() -> None:
    asset_id = uuid4()
    version_id = uuid4()
    blob_id = uuid4()
    expires_at = datetime.now(UTC) + timedelta(seconds=60)

    class Store:
        async def authorize(self, requested_asset_id, requested_version_id, context):
            assert requested_asset_id == asset_id
            assert requested_version_id == version_id
            return AssetDownloadResult(
                asset_id=asset_id,
                asset_version_id=version_id,
                blob_id=blob_id,
                filename="datasheet.pdf",
                content_type="application/pdf",
                byte_size=128,
                sha256="a" * 64,
                grant=DownloadGrant(
                    url="https://storage.example.invalid/private?signed=true",
                    expires_at=expires_at,
                ),
            )

    app.dependency_overrides[get_asset_download_store] = lambda: Store()
    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/assets/{asset_id}/versions/{version_id}/download",
                headers={
                    "X-Grovello-Dev-Subject": "northstar-analyst",
                    "X-Grovello-Dev-Session": "download-session",
                    "X-Workspace-ID": str(NORTHSTAR_WORKSPACE_ID),
                },
            )
    finally:
        app.dependency_overrides.pop(get_asset_download_store, None)
    assert response.status_code == 200
    assert response.json()["data"]["blobId"] == str(blob_id)
    assert response.json()["data"]["url"].endswith("signed=true")
    assert response.json()["data"]["expiresAt"] == expires_at.isoformat().replace("+00:00", "Z")
