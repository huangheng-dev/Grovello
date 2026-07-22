from collections.abc import Iterator
from typing import Annotated

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from grovello.access import NORTHSTAR_WORKSPACE_ID, SANDBOX_WORKSPACE_ID, AuthorizedWorkspace
from grovello.api.dependencies import get_business_truth_store, require_workspace_access
from grovello.business_truth import (
    BusinessTruthStore,
    InMemoryBusinessTruthStore,
    northstar_business_truth_store,
)
from grovello.main import app

NORTHSTAR_ID = str(NORTHSTAR_WORKSPACE_ID)
SANDBOX_ID = str(SANDBOX_WORKSPACE_ID)


def session_headers(
    subject: str,
    workspace_id: str,
    idempotency_key: str | None = None,
) -> dict[str, str]:
    headers = {
        "X-Grovello-Dev-Subject": subject,
        "X-Grovello-Dev-Session": f"session-{subject}",
        "X-Request-ID": f"request-{subject}",
        "X-Workspace-ID": workspace_id,
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return headers


@pytest.fixture
def truth_client() -> Iterator[tuple[TestClient, dict]]:
    stores = {
        NORTHSTAR_WORKSPACE_ID: northstar_business_truth_store(NORTHSTAR_WORKSPACE_ID),
        SANDBOX_WORKSPACE_ID: InMemoryBusinessTruthStore(SANDBOX_WORKSPACE_ID),
    }

    async def override_store(
        access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    ) -> BusinessTruthStore:
        return stores[access.workspace.id]

    app.dependency_overrides[get_business_truth_store] = override_store
    try:
        with TestClient(app) as client:
            yield client, stores
    finally:
        app.dependency_overrides.pop(get_business_truth_store, None)


def create_payload(
    object_type: str,
    slug: str,
    name: str,
    citations: list[dict] | None = None,
) -> dict:
    structured_payloads = {
        "evidence": {
            "evidenceType": "technical_record",
            "sourceTitle": name,
            "collectedAt": "2026-07-21",
            "sourceLocale": "en",
            "verificationStatus": "owner_attested",
            "reliability": "medium",
            "usageRights": "owner_provided",
            "scope": "Fictional test contract",
            "evidenceSummary": "Evidence used to verify the shared business truth contract.",
            "keyFindings": ["The test contract can pin an exact evidence version."],
        },
        "knowledge_document": {
            "documentType": "technical_document",
            "sourceLocale": "en",
            "ownerTeam": "Product operations",
            "knowledgeStatus": "working",
            "documentSummary": "Knowledge used to verify the shared business truth contract.",
            "knowledgeBody": "This is fictional test content.",
            "topics": ["business truth"],
            "retrievalKeywords": ["test contract"],
        },
        "case_study": {
            "caseStudyType": "pilot",
            "disclosureStatus": "fictional_fixture",
            "customerDisplayName": "Fictional acceptance customer",
            "customerIndustry": "Industrial automation",
            "marketId": "11111111-1111-4111-8111-111111111111",
            "productId": "22222222-2222-4222-8222-222222222222",
            "engagementStartedAt": "2026-01-15",
            "caseSummary": "A fictional case used only to verify governed case-study records.",
            "challenge": "Verify that customer outcomes cannot be stored as unsupported marketing claims.",
            "approach": "Store structured outcomes and pin every active case to evidence.",
            "outcomes": [
                {
                    "metric": "Acceptance coverage",
                    "result": "One governed workflow",
                    "period": "2026 fixture",
                    "evidenceNote": "Supported by the cited fictional acceptance record",
                }
            ],
            "lessons": ["Keep outcomes separate from unsupported claims."],
            "limitations": ["This is not a real customer result."],
            "approvedUseCases": ["Product workflow acceptance"],
            "authorizationReference": "fictional-fixture",
            "ownerTeam": "Product operations",
        },
    }
    return {
        "objectType": object_type,
        "slug": slug,
        "name": name,
        "status": "active",
        "locale": "en",
        "payload": structured_payloads.get(
            object_type,
            {"verificationState": "test_contract"},
        ),
        "businessPurpose": "Verify the shared business truth contract",
        "changeSummary": f"Create {name}",
        "sourceType": "owner_edit",
        "inputVersions": {},
        "citations": citations or [],
    }


@pytest.mark.parametrize("object_type", ["evidence", "knowledge_document", "case_study"])
def test_structured_knowledge_payload_is_enforced_by_domain_service(
    truth_client,
    object_type: str,
) -> None:
    client, _stores = truth_client
    slug_type = object_type.replace("_", "-")
    payload = create_payload(object_type, f"invalid-{slug_type}", f"Invalid {object_type}")
    payload["payload"] = {}

    response = client.post(
        "/api/v1/business-truth/objects",
        headers=session_headers("northstar-owner", NORTHSTAR_ID, f"invalid-{slug_type}"),
        json=payload,
    )

    assert response.status_code == 422
    assert "missing required fields" in response.json()["detail"]


def test_active_case_study_requires_and_pins_exact_evidence(truth_client) -> None:
    client, _stores = truth_client
    profile = client.get(
        "/api/v1/business-truth/profile",
        headers=session_headers("northstar-analyst", NORTHSTAR_ID),
    ).json()["data"]
    evidence = next(item for item in profile["objects"] if item["objectType"] == "evidence")
    market = next(item for item in profile["objects"] if item["objectType"] == "market")
    product = next(item for item in profile["objects"] if item["objectType"] == "product")
    payload = create_payload(
        "case_study",
        "governed-case-study",
        "Governed fictional case study",
    )
    payload["payload"]["marketId"] = market["id"]
    payload["payload"]["productId"] = product["id"]

    unsupported = client.post(
        "/api/v1/business-truth/objects",
        headers=session_headers("northstar-owner", NORTHSTAR_ID, "case-without-evidence"),
        json=payload,
    )

    assert unsupported.status_code == 422
    assert unsupported.json()["detail"] == (
        "An active case_study must cite at least one exact evidence version"
    )

    payload["citations"] = [
        {
            "evidenceVersionId": evidence["version"]["id"],
            "claimText": "This fictional record supports the stated workflow outcome.",
            "locator": {"section": "acceptance-evidence"},
        }
    ]
    created = client.post(
        "/api/v1/business-truth/objects",
        headers=session_headers("northstar-owner", NORTHSTAR_ID, "case-with-evidence"),
        json=payload,
    )

    assert created.status_code == 201
    case_study = created.json()["data"]["object"]
    assert case_study["version"]["payload"]["outcomes"][0]["metric"] == "Acceptance coverage"
    assert case_study["version"]["citations"][0]["evidenceVersionId"] == evidence["version"]["id"]


def test_profile_contract_is_complete_and_seed_labeled(truth_client) -> None:
    client, _stores = truth_client
    response = client.get(
        "/api/v1/business-truth/profile",
        headers=session_headers("northstar-analyst", NORTHSTAR_ID),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["source"] == "seed"
    assert body["data"]["validationState"] == "complete"
    assert body["data"]["objectCount"] == 10
    assert body["data"]["citationCount"] == 1
    assert body["data"]["missingObjectTypes"] == []


def test_write_requires_permission_and_idempotency_key(truth_client) -> None:
    client, _stores = truth_client
    payload = create_payload("brand", "analyst-brand", "Analyst brand")

    denied = client.post(
        "/api/v1/business-truth/objects",
        headers=session_headers("northstar-analyst", NORTHSTAR_ID, "analyst-write"),
        json=payload,
    )
    missing_key = client.post(
        "/api/v1/business-truth/objects",
        headers=session_headers("northstar-owner", NORTHSTAR_ID),
        json=payload,
    )

    assert denied.status_code == 403
    assert missing_key.status_code == 400
    assert missing_key.json()["detail"] == "Idempotency-Key is required"


def test_create_and_cite_exact_evidence_version_is_idempotent(truth_client) -> None:
    client, _stores = truth_client
    evidence_payload = create_payload(
        "evidence",
        "germany-market-evidence",
        "Germany market evidence",
    )
    evidence_response = client.post(
        "/api/v1/business-truth/objects",
        headers=session_headers("northstar-owner", NORTHSTAR_ID, "create-market-evidence"),
        json=evidence_payload,
    )
    assert evidence_response.status_code == 201
    evidence_version_id = evidence_response.json()["data"]["object"]["version"]["id"]

    product_payload = create_payload(
        "product",
        "precision-controller-p300",
        "Precision Controller P300",
        citations=[
            {
                "evidenceVersionId": evidence_version_id,
                "claimText": "The fictional acceptance fixture records a 24-month warranty.",
                "locator": {"section": "commercial-terms", "paragraph": 2},
            }
        ],
    )
    headers = session_headers("northstar-owner", NORTHSTAR_ID, "create-p300")
    created = client.post(
        "/api/v1/business-truth/objects",
        headers=headers,
        json=product_payload,
    )
    replayed = client.post(
        "/api/v1/business-truth/objects",
        headers=headers,
        json=product_payload,
    )

    assert created.status_code == 201
    assert replayed.status_code == 201
    created_data = created.json()["data"]
    replayed_data = replayed.json()["data"]
    assert created_data["idempotentReplay"] is False
    assert replayed_data["idempotentReplay"] is True
    assert replayed_data["object"]["id"] == created_data["object"]["id"]
    citation = created_data["object"]["version"]["citations"][0]
    assert citation["evidenceVersionId"] == evidence_version_id
    assert citation["evidenceVersion"] == 1


def test_historical_versions_are_retrievable(truth_client) -> None:
    client, _stores = truth_client
    created = client.post(
        "/api/v1/business-truth/objects",
        headers=session_headers("northstar-owner", NORTHSTAR_ID, "create-versioned-brand"),
        json=create_payload("brand", "versioned-brand", "Versioned Brand"),
    )
    object_id = created.json()["data"]["object"]["id"]
    version_payload = {
        "name": "Versioned Brand International",
        "status": "active",
        "locale": "en",
        "payload": {"positioning": "Global B2B growth"},
        "businessPurpose": "Localize the approved brand positioning",
        "changeSummary": "Add international positioning",
        "sourceType": "owner_edit",
        "inputVersions": {"previous": 1},
        "citations": [],
    }
    versioned = client.post(
        f"/api/v1/business-truth/objects/{object_id}/versions",
        headers=session_headers("northstar-owner", NORTHSTAR_ID, "version-brand-v2"),
        json=version_payload,
    )
    historical = client.get(
        f"/api/v1/business-truth/objects/{object_id}?version=1",
        headers=session_headers("northstar-analyst", NORTHSTAR_ID),
    )
    current = client.get(
        f"/api/v1/business-truth/objects/{object_id}",
        headers=session_headers("northstar-analyst", NORTHSTAR_ID),
    )

    assert versioned.status_code == 201
    assert versioned.json()["data"]["object"]["version"]["version"] == 2
    assert historical.json()["data"]["currentVersion"] == 2
    assert historical.json()["data"]["version"]["name"] == "Versioned Brand"
    assert current.json()["data"]["version"]["name"] == "Versioned Brand International"


def test_cross_tenant_business_object_is_hidden(truth_client) -> None:
    client, _stores = truth_client
    created = client.post(
        "/api/v1/business-truth/objects",
        headers=session_headers("northstar-owner", NORTHSTAR_ID, "create-private-brand"),
        json=create_payload("brand", "private-brand", "Private Brand"),
    )
    object_id = created.json()["data"]["object"]["id"]

    response = client.get(
        f"/api/v1/business-truth/objects/{object_id}",
        headers=session_headers("sandbox-owner", SANDBOX_ID),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Business object not found"


def test_citation_rejects_non_evidence_version(truth_client) -> None:
    client, _stores = truth_client
    brand = client.post(
        "/api/v1/business-truth/objects",
        headers=session_headers("northstar-owner", NORTHSTAR_ID, "create-citation-brand"),
        json=create_payload("brand", "citation-brand", "Citation Brand"),
    )
    brand_version_id = brand.json()["data"]["object"]["version"]["id"]

    response = client.post(
        "/api/v1/business-truth/objects",
        headers=session_headers("northstar-owner", NORTHSTAR_ID, "invalid-citation"),
        json=create_payload(
            "product",
            "invalid-citation-product",
            "Invalid Citation Product",
            citations=[
                {
                    "evidenceVersionId": brand_version_id,
                    "claimText": "This must not accept a brand as evidence.",
                    "locator": {},
                }
            ],
        ),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Citations must reference a versioned evidence object"


def test_empty_workspace_reports_validation_gaps(truth_client) -> None:
    client, _stores = truth_client
    response = client.get(
        "/api/v1/business-truth/profile",
        headers=session_headers("sandbox-owner", SANDBOX_ID),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["validationState"] == "incomplete"
    assert data["objectCount"] == 0
    assert len(data["missingObjectTypes"]) == 10
