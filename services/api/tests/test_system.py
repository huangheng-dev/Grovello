from fastapi.testclient import TestClient

from grovello.api.dependencies import get_asset_scanner, get_object_storage
from grovello.asset_scanner import AssetScannerHealth
from grovello.main import app
from grovello.object_storage import ObjectStorageHealth

client = TestClient(app)


def test_health_envelope_and_request_id() -> None:
    response = client.get("/api/v1/system/health", headers={"X-Request-ID": "test-request"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request"
    payload = response.json()
    assert payload["data"]["status"] == "ok"
    assert payload["meta"]["requestId"] == "test-request"


def test_ten_product_domains_are_exposed() -> None:
    response = client.get("/api/v1/system/capabilities")
    capabilities = response.json()["data"]
    assert len(capabilities) == 10
    assert {item["key"] for item in capabilities} == {
        "command",
        "brand",
        "content",
        "channels",
        "pipeline",
        "revenue",
        "customer",
        "data",
        "automation",
        "governance",
    }


def test_object_storage_health_is_honest_when_not_configured() -> None:
    response = client.get("/api/v1/system/object-storage/health")
    assert response.status_code == 200
    assert response.json()["data"] == {
        "status": "degraded",
        "service": "object-storage",
        "provider": "s3-compatible",
        "configured": False,
        "detail": "not_configured",
    }


def test_object_storage_health_uses_the_provider_adapter() -> None:
    class HealthyStorage:
        async def health(self) -> ObjectStorageHealth:
            return ObjectStorageHealth(available=True, provider="test-s3")

    app.dependency_overrides[get_object_storage] = lambda: HealthyStorage()
    try:
        response = client.get("/api/v1/system/object-storage/health")
    finally:
        app.dependency_overrides.pop(get_object_storage, None)

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ok"
    assert response.json()["data"]["provider"] == "test-s3"
    assert response.json()["data"]["configured"] is True


def test_asset_scanner_health_is_honest_and_uses_adapter() -> None:
    response = client.get("/api/v1/system/asset-scanner/health")
    assert response.json()["data"] == {
        "status": "degraded",
        "service": "asset-scanner",
        "provider": "clamav",
        "configured": False,
        "detail": "not_configured",
    }

    class HealthyScanner:
        async def health(self) -> AssetScannerHealth:
            return AssetScannerHealth(available=True, provider="test-scanner")

    app.dependency_overrides[get_asset_scanner] = lambda: HealthyScanner()
    try:
        response = client.get("/api/v1/system/asset-scanner/health")
    finally:
        app.dependency_overrides.pop(get_asset_scanner, None)
    assert response.json()["data"]["status"] == "ok"
    assert response.json()["data"]["provider"] == "test-scanner"
