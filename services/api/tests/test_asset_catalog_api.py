from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from grovello.access import NORTHSTAR_WORKSPACE_ID
from grovello.api.dependencies import get_asset_catalog_store
from grovello.asset_catalog import (
    AssetCatalogNotFoundError,
    AssetCatalogRecord,
    AssetFileRecord,
    AssetVersionRecord,
)
from grovello.main import app

ASSET_ID = UUID("11111111-1111-4111-8111-111111111111")
VERSION_ID = UUID("22222222-2222-4222-8222-222222222222")
BLOB_ID = UUID("33333333-3333-4333-8333-333333333333")


def headers(subject: str = "northstar-analyst") -> dict[str, str]:
    return {
        "X-Grovello-Dev-Subject": subject,
        "X-Grovello-Dev-Session": f"session-{subject}",
        "X-Workspace-ID": str(NORTHSTAR_WORKSPACE_ID),
    }


def catalog_record() -> AssetCatalogRecord:
    now = datetime.now(UTC)
    file = AssetFileRecord(
        blob_id=BLOB_ID,
        filename="controller.pdf",
        content_type="application/pdf",
        byte_size=128,
        sha256="a" * 64,
        scan_status="clean",
        storage_status="available",
    )
    version = AssetVersionRecord(
        id=VERSION_ID,
        version=1,
        name="Controller datasheet",
        status="active",
        locale="en",
        payload={"originalFilename": "controller.pdf"},
        change_summary="Initial governed asset",
        created_at=now,
        original_file=file,
        downloadable=True,
    )
    return AssetCatalogRecord(
        id=ASSET_ID,
        slug="controller-datasheet",
        name="Controller datasheet",
        status="active",
        current_version=1,
        updated_at=now,
        versions=(version,),
    )


class FakeCatalogStore:
    async def list_assets(self, limit: int):
        assert limit == 50
        return (catalog_record(),)

    async def get_asset(self, asset_id, version_limit: int):
        assert version_limit == 50
        if asset_id != ASSET_ID:
            raise AssetCatalogNotFoundError("Asset was not found")
        return catalog_record()


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_asset_catalog_store] = lambda: FakeCatalogStore()
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_asset_catalog_store, None)


def test_asset_catalog_exposes_safe_version_metadata(client: TestClient) -> None:
    response = client.get("/api/v1/assets", headers=headers())
    assert response.status_code == 200
    item = response.json()["data"]["items"][0]
    assert item["id"] == str(ASSET_ID)
    assert item["versions"][0]["downloadable"] is True
    assert item["versions"][0]["originalFile"]["scanStatus"] == "clean"
    assert "objectKey" not in item["versions"][0]["originalFile"]
    assert "providerVersionId" not in item["versions"][0]["originalFile"]


def test_asset_detail_returns_version_history(client: TestClient) -> None:
    response = client.get(f"/api/v1/assets/{ASSET_ID}", headers=headers())
    assert response.status_code == 200
    assert response.json()["data"]["versions"][0]["id"] == str(VERSION_ID)


def test_asset_detail_not_found_is_explicit(client: TestClient) -> None:
    response = client.get(f"/api/v1/assets/{UUID(int=9)}", headers=headers())
    assert response.status_code == 404
    assert response.json()["detail"] == "Asset was not found"
