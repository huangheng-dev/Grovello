from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from grovello.access import NORTHSTAR_WORKSPACE_ID
from grovello.api.dependencies import get_knowledge_store
from grovello.knowledge import (
    KnowledgeConflictError,
    KnowledgeGenerationRecord,
    KnowledgeIngestionMutationResult,
    KnowledgeIngestionRecord,
    KnowledgeNotFoundError,
    KnowledgeSourceSnapshotRecord,
)
from grovello.main import app

INGESTION_ID = UUID("10000000-0000-4000-8000-000000000001")
SNAPSHOT_ID = UUID("20000000-0000-4000-8000-000000000001")
GENERATION_ID = UUID("30000000-0000-4000-8000-000000000001")
SOURCE_OBJECT_ID = UUID("40000000-0000-4000-8000-000000000001")
SOURCE_VERSION_ID = UUID("50000000-0000-4000-8000-000000000001")
MISSING_ID = UUID("60000000-0000-4000-8000-000000000001")


def headers(subject: str, idempotency_key: str | None = None) -> dict[str, str]:
    result = {
        "X-Grovello-Dev-Subject": subject,
        "X-Grovello-Dev-Session": f"session-{subject}",
        "X-Request-ID": f"request-{subject}",
        "X-Workspace-ID": str(NORTHSTAR_WORKSPACE_ID),
    }
    if idempotency_key:
        result["Idempotency-Key"] = idempotency_key
    return result


def ingestion_record() -> KnowledgeIngestionRecord:
    now = datetime.now(UTC)
    return KnowledgeIngestionRecord(
        id=INGESTION_ID,
        workspace_id=NORTHSTAR_WORKSPACE_ID,
        source_object_id=SOURCE_OBJECT_ID,
        source_version_id=SOURCE_VERSION_ID,
        source_object_type="knowledge_document",
        actor_id="northstar-owner",
        business_purpose="Index the approved product knowledge",
        pipeline_profile="canonical-text-v1",
        pipeline_version="1",
        status="pending",
        input_versions={"businessProfile": "1"},
        approval_policy_version=1,
        workflow_id=None,
        workflow_run_id=None,
        cost_summary={},
        failure_code=None,
        failure_detail=None,
        created_at=now,
        updated_at=now,
        snapshot=KnowledgeSourceSnapshotRecord(
            id=SNAPSHOT_ID,
            source_object_id=SOURCE_OBJECT_ID,
            source_version_id=SOURCE_VERSION_ID,
            source_object_type="knowledge_document",
            content_sha256="a" * 64,
            locale="en",
            source_status="active",
            usage_rights="internal_only",
            sensitivity="internal",
            parser_eligible=True,
            source_locator={
                "sourceObjectId": str(SOURCE_OBJECT_ID),
                "sourceVersionId": str(SOURCE_VERSION_ID),
            },
            source_metadata={"objectVersion": 1},
            policy_version=1,
            created_at=now,
        ),
        generation=KnowledgeGenerationRecord(
            id=GENERATION_ID,
            status="pending",
            pipeline_profile="canonical-text-v1",
            pipeline_version="1",
            parser_profile="canonical-json-v1",
            normalizer_version="none",
            classifier_version="none",
            chunker_version="none",
            embedding_config={},
            chunk_count=0,
            warnings=[],
            created_at=now,
            updated_at=now,
        ),
    )


class FakeKnowledgeStore:
    def __init__(self) -> None:
        self.item = ingestion_record()
        self.idempotency_key: str | None = None
        self.request_source: tuple[UUID, UUID] | None = None

    async def create_ingestion(self, command, context):
        if command.pipeline_profile == "conflict-profile":
            raise KnowledgeConflictError("Knowledge source version is not eligible")
        replay = self.idempotency_key == context.idempotency_key
        self.idempotency_key = context.idempotency_key
        self.request_source = (command.source_object_id, command.source_version_id)
        return KnowledgeIngestionMutationResult(self.item, replay)

    async def list_ingestions(self, limit):
        return (self.item,)

    async def get_ingestion(self, ingestion_id):
        if ingestion_id == MISSING_ID:
            raise KnowledgeNotFoundError("Knowledge ingestion was not found")
        return self.item


@pytest.fixture
def knowledge_client() -> Iterator[tuple[TestClient, FakeKnowledgeStore]]:
    store = FakeKnowledgeStore()
    app.dependency_overrides[get_knowledge_store] = lambda: store
    try:
        with TestClient(app) as client:
            yield client, store
    finally:
        app.dependency_overrides.pop(get_knowledge_store, None)


def payload(profile: str = "canonical-text-v1") -> dict:
    return {
        "sourceObjectId": str(SOURCE_OBJECT_ID),
        "sourceVersionId": str(SOURCE_VERSION_ID),
        "businessPurpose": "Index the approved product knowledge",
        "pipelineProfile": profile,
        "pipelineVersion": "1",
        "inputVersions": {"businessProfile": "1"},
        "approvalPolicyVersion": 1,
    }


def test_owner_creates_idempotent_pending_ingestion(knowledge_client) -> None:
    client, store = knowledge_client
    first = client.post(
        "/api/v1/knowledge/ingestions",
        headers=headers("northstar-owner", "knowledge-ingestion-1"),
        json=payload(),
    )
    replay = client.post(
        "/api/v1/knowledge/ingestions",
        headers=headers("northstar-owner", "knowledge-ingestion-1"),
        json=payload(),
    )

    assert first.status_code == 201
    assert replay.status_code == 201
    assert first.json()["data"]["ingestion"]["status"] == "pending"
    assert first.json()["data"]["ingestion"]["generation"]["embeddingConfig"] == {}
    assert first.json()["data"]["ingestion"]["generation"]["chunkCount"] == 0
    assert first.json()["data"]["idempotentReplay"] is False
    assert replay.json()["data"]["idempotentReplay"] is True
    assert store.request_source == (SOURCE_OBJECT_ID, SOURCE_VERSION_ID)


def test_ingestion_requires_idempotency_and_narrow_permission(knowledge_client) -> None:
    client, _store = knowledge_client
    missing_key = client.post(
        "/api/v1/knowledge/ingestions",
        headers=headers("northstar-owner"),
        json=payload(),
    )
    analyst = client.post(
        "/api/v1/knowledge/ingestions",
        headers=headers("northstar-analyst", "analyst-ingestion"),
        json=payload(),
    )

    assert missing_key.status_code == 400
    assert missing_key.json()["detail"] == "Idempotency-Key is required"
    assert analyst.status_code == 403
    assert analyst.json()["detail"] == "Permission required: knowledge.ingest"


def test_analyst_can_list_and_read_ingestion_without_sensitive_chunk_data(
    knowledge_client,
) -> None:
    client, _store = knowledge_client
    listing = client.get(
        "/api/v1/knowledge/ingestions",
        headers=headers("northstar-analyst"),
    )
    detail = client.get(
        f"/api/v1/knowledge/ingestions/{INGESTION_ID}",
        headers=headers("northstar-analyst"),
    )

    assert listing.status_code == 200
    assert listing.json()["data"]["items"][0]["id"] == str(INGESTION_ID)
    assert detail.status_code == 200
    data = detail.json()["data"]
    assert data["snapshot"]["contentSha256"] == "a" * 64
    assert "text" not in data["snapshot"]
    assert data["generation"]["status"] == "pending"


def test_knowledge_store_errors_map_to_bounded_http_states(knowledge_client) -> None:
    client, _store = knowledge_client
    conflict = client.post(
        "/api/v1/knowledge/ingestions",
        headers=headers("northstar-owner", "conflicting-ingestion"),
        json=payload("conflict-profile"),
    )
    missing = client.get(
        f"/api/v1/knowledge/ingestions/{MISSING_ID}",
        headers=headers("northstar-analyst"),
    )

    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "Knowledge source version is not eligible"
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Knowledge ingestion was not found"


def test_knowledge_chunks_have_no_public_creation_route(knowledge_client) -> None:
    client, _store = knowledge_client
    openapi = client.get("/openapi.json").json()

    assert "/api/v1/knowledge/ingestions" in openapi["paths"]
    assert not any(
        path.startswith("/api/v1/knowledge/chunks") for path in openapi["paths"]
    )
