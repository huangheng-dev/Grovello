from fastapi.testclient import TestClient

from grovello.main import app

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
