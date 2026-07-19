from fastapi.testclient import TestClient

from grovello.config import get_settings
from grovello.main import app

client = TestClient(app)

NORTHSTAR_ID = "00000000-0000-4000-8000-000000000001"
SANDBOX_ID = "00000000-0000-4000-8000-000000000002"


def session_headers(subject: str, workspace_id: str | None = None) -> dict[str, str]:
    headers = {
        "X-Grovello-Dev-Subject": subject,
        "X-Grovello-Dev-Session": f"session-{subject}",
        "X-Request-ID": f"request-{subject}",
    }
    if workspace_id:
        headers["X-Workspace-ID"] = workspace_id
    return headers


def test_workspace_list_requires_an_authenticated_session() -> None:
    response = client.get("/api/v1/workspaces")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "GrovelloDevelopmentSession"


def test_development_identity_is_rejected_in_production(monkeypatch) -> None:
    monkeypatch.setenv("GROVELLO_ENVIRONMENT", "production")
    get_settings.cache_clear()
    try:
        response = client.get(
            "/api/v1/workspaces",
            headers=session_headers("northstar-owner"),
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "OIDC session verification is not configured"
    finally:
        get_settings.cache_clear()


def test_workspace_list_is_scoped_to_membership() -> None:
    owner_response = client.get("/api/v1/workspaces", headers=session_headers("northstar-owner"))
    sandbox_response = client.get("/api/v1/workspaces", headers=session_headers("sandbox-owner"))

    assert owner_response.status_code == 200
    assert [item["id"] for item in owner_response.json()["data"]] == [NORTHSTAR_ID]
    assert [item["id"] for item in sandbox_response.json()["data"]] == [SANDBOX_ID]


def test_cross_tenant_workspace_is_hidden() -> None:
    response = client.get(
        f"/api/v1/workspaces/{SANDBOX_ID}",
        headers=session_headers("northstar-owner"),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def test_access_summary_resolves_roles_and_permissions() -> None:
    response = client.get(
        "/api/v1/workspaces/current/access",
        headers=session_headers("northstar-analyst", NORTHSTAR_ID),
    )
    assert response.status_code == 200
    access = response.json()["data"]
    assert access["workspace"]["id"] == NORTHSTAR_ID
    assert access["roles"] == ["growth_analyst"]
    assert "workspace.read" in access["permissions"]
    assert "audit.read" not in access["permissions"]


def test_malformed_workspace_header_is_rejected() -> None:
    response = client.get(
        "/api/v1/workspaces/current/access",
        headers=session_headers("northstar-owner", "not-a-uuid"),
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "X-Workspace-ID must be a UUID"


def test_audit_read_requires_permission_and_carries_lineage() -> None:
    denied = client.get(
        "/api/v1/workspaces/current/audit-events",
        headers=session_headers("northstar-analyst", NORTHSTAR_ID),
    )
    allowed = client.get(
        "/api/v1/workspaces/current/audit-events",
        headers=session_headers("northstar-owner", NORTHSTAR_ID),
    )

    assert denied.status_code == 403
    assert allowed.status_code == 200
    event = allowed.json()["data"][0]
    assert event["workspaceId"] == NORTHSTAR_ID
    assert event["actorId"] == "northstar-owner"
    assert event["sessionId"] == "session-northstar-owner"
    assert event["requestId"] == "request-northstar-owner"
    assert event["outcome"] == "allowed"


def test_recovery_plan_is_restricted_to_workspace_owner() -> None:
    denied = client.get(
        "/api/v1/workspaces/current/recovery-plan",
        headers=session_headers("northstar-analyst", NORTHSTAR_ID),
    )
    allowed = client.get(
        "/api/v1/workspaces/current/recovery-plan",
        headers=session_headers("northstar-owner", NORTHSTAR_ID),
    )

    assert denied.status_code == 403
    assert allowed.status_code == 200
    plan = allowed.json()["data"]
    assert plan["status"] == "ready"
    assert plan["requiredPermission"] == "workspace.recover"
    assert len(plan["safeguards"]) == 4
