import runpy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from pydantic import ValidationError

from grovello.access import OWNER_PERMISSIONS, access_directory
from grovello.business_truth import (
    CreateBusinessObjectCommand,
    InMemoryBusinessTruthStore,
    InvalidBusinessTruthPayloadError,
    MutationContext,
)
from grovello.knowledge import (
    CreateKnowledgeIngestionCommand,
    CreatePipelineChunkCommand,
    KnowledgeConflictError,
    KnowledgeMutationContext,
    SqlAlchemyKnowledgeStore,
)
from grovello.models import (
    AuditEvent,
    Base,
    BusinessObject,
    BusinessObjectVersion,
    KnowledgeGenerationChunk,
    KnowledgeIngestion,
    OutboxEvent,
)
from grovello.schemas import BusinessObjectCreate

WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000001")
GENERATION_ID = UUID("10000000-0000-4000-8000-000000000001")
INGESTION_ID = UUID("20000000-0000-4000-8000-000000000001")
SNAPSHOT_ID = UUID("30000000-0000-4000-8000-000000000001")
SOURCE_OBJECT_ID = UUID("40000000-0000-4000-8000-000000000001")
SOURCE_VERSION_ID = UUID("50000000-0000-4000-8000-000000000001")


def test_knowledge_tables_are_canonical_tenant_metadata() -> None:
    expected = {
        "knowledge_ingestions",
        "knowledge_source_snapshots",
        "knowledge_generations",
        "knowledge_generation_chunks",
        "knowledge_retrieval_receipts",
    }
    assert expected <= set(Base.metadata.tables)

    generation_chunks = Base.metadata.tables["knowledge_generation_chunks"]
    foreign_key_targets = {
        tuple(sorted(element.target_fullname for element in constraint.elements))
        for constraint in generation_chunks.foreign_key_constraints
    }
    assert (
        "business_object_versions.id",
        "business_object_versions.object_id",
        "business_object_versions.workspace_id",
    ) in foreign_key_targets
    assert (
        "knowledge_generations.id",
        "knowledge_generations.workspace_id",
    ) in foreign_key_targets


def test_knowledge_migration_enables_forced_rls_and_pipeline_lineage() -> None:
    migration_path = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "0012_knowledge_ingestion_foundation.py"
    )
    migration = runpy.run_path(str(migration_path))
    assert migration["down_revision"] == "0011"
    assert migration["TENANT_TABLES"] == (
        "knowledge_ingestions",
        "knowledge_source_snapshots",
        "knowledge_generations",
        "knowledge_generation_chunks",
        "knowledge_retrieval_receipts",
    )
    source = migration_path.read_text(encoding="utf-8")
    assert "source_type IN ('owner_edit', 'import', 'seed', 'pipeline')" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "current_setting('app.workspace_id'" in source
    assert "DROP POLICY IF EXISTS" in source
    assert "DELETE FROM business_objects AS object" in source


def test_knowledge_permissions_follow_narrow_risk_tiers() -> None:
    migration_path = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "0012_knowledge_ingestion_foundation.py"
    )
    permissions = {
        key: risk
        for key, _description, risk in runpy.run_path(str(migration_path))[
            "KNOWLEDGE_PERMISSIONS"
        ]
    }
    assert permissions == {
        "knowledge.retrieve": "R0",
        "knowledge.ingest": "R1",
        "knowledge.reindex": "R1",
        "knowledge.cancel": "R1",
        "knowledge.retire": "R2",
        "knowledge.sensitive.read": "R2",
        "knowledge.admin": "R2",
    }
    assert set(permissions) <= OWNER_PERMISSIONS
    analyst = access_directory._grants[("northstar-analyst", WORKSPACE_ID)]
    assert "knowledge.retrieve" in analyst.permissions
    assert "knowledge.ingest" not in analyst.permissions
    assert "knowledge.sensitive.read" not in analyst.permissions


@pytest.mark.asyncio
async def test_public_business_truth_cannot_create_pipeline_chunks() -> None:
    store = InMemoryBusinessTruthStore(WORKSPACE_ID)
    with pytest.raises(InvalidBusinessTruthPayloadError, match="governed knowledge pipeline"):
        await store.create_object(
            CreateBusinessObjectCommand(
                object_type="knowledge_chunk",
                slug="owner-authored-chunk",
                name="Owner-authored chunk",
                status="draft",
                locale="en",
                payload={"text": "This must not be accepted."},
                business_purpose="Attempt to bypass the knowledge pipeline",
                change_summary="Attempt owner-authored chunk creation",
                source_type="owner_edit",
                source_ref=None,
                input_versions={},
                citations=(),
            ),
            MutationContext(
                actor_type="user",
                actor_id="northstar-owner",
                session_id="session-owner",
                request_id="request-owner",
                idempotency_key="owner-authored-chunk",
            ),
        )

    with pytest.raises(ValidationError):
        BusinessObjectCreate.model_validate(
            {
                "objectType": "knowledge_document",
                "slug": "pipeline-source-attempt",
                "name": "Pipeline source attempt",
                "status": "draft",
                "locale": "en",
                "payload": {},
                "businessPurpose": "Attempt to set an internal source type",
                "changeSummary": "Attempt internal source type",
                "sourceType": "pipeline",
                "inputVersions": {},
                "citations": [],
            }
        )


@pytest.mark.asyncio
async def test_pipeline_chunk_creation_requires_service_actor() -> None:
    store = SqlAlchemyKnowledgeStore(SimpleNamespace(), WORKSPACE_ID)
    with pytest.raises(KnowledgeConflictError, match="pipeline service"):
        await store.create_pipeline_chunk(
            CreatePipelineChunkCommand(
                generation_id=GENERATION_ID,
                ordinal=1,
                text="Governed source text",
                locator={"section": "overview"},
                locale="en",
            ),
            KnowledgeMutationContext(
                actor_type="user",
                actor_id="northstar-owner",
                session_id="session-owner",
                request_id="request-owner",
                idempotency_key="chunk-user-attempt",
            ),
        )


@pytest.mark.asyncio
async def test_ingestion_idempotency_key_rejects_a_different_request() -> None:
    existing = KnowledgeIngestion(
        id=INGESTION_ID,
        workspace_id=WORKSPACE_ID,
        source_object_id=SOURCE_OBJECT_ID,
        source_version_id=SOURCE_VERSION_ID,
        source_object_type="knowledge_document",
        actor_id="northstar-owner",
        idempotency_key="knowledge-ingestion",
        request_hash="f" * 64,
        business_purpose="Index the approved product knowledge",
        pipeline_profile="canonical-text-v1",
        pipeline_version="1",
        status="pending",
        input_versions={},
        cost_summary={},
    )
    session = SimpleNamespace(scalar=AsyncMock(return_value=existing))
    store = SqlAlchemyKnowledgeStore(session, WORKSPACE_ID)

    with pytest.raises(KnowledgeConflictError, match="different knowledge ingestion"):
        await store.create_ingestion(
            CreateKnowledgeIngestionCommand(
                source_object_id=SOURCE_OBJECT_ID,
                source_version_id=SOURCE_VERSION_ID,
                business_purpose="Index the approved product knowledge",
                pipeline_profile="canonical-text-v1",
                pipeline_version="1",
                input_versions={},
                approval_policy_version=1,
            ),
            KnowledgeMutationContext(
                actor_type="user",
                actor_id="northstar-owner",
                session_id="session-owner",
                request_id="request-owner",
                idempotency_key="knowledge-ingestion",
            ),
        )


@pytest.mark.asyncio
async def test_pipeline_chunk_is_immutable_draft_with_audit_and_outbox() -> None:
    generation = SimpleNamespace(
        id=GENERATION_ID,
        workspace_id=WORKSPACE_ID,
        ingestion_id=INGESTION_ID,
        source_snapshot_id=SNAPSHOT_ID,
        status="pending",
        pipeline_profile="canonical-text-v1",
        pipeline_version="1",
        chunk_count=0,
    )
    snapshot = SimpleNamespace(
        id=SNAPSHOT_ID,
        workspace_id=WORKSPACE_ID,
        source_object_id=SOURCE_OBJECT_ID,
        source_version_id=SOURCE_VERSION_ID,
    )
    session = SimpleNamespace(
        scalar=AsyncMock(side_effect=[None, generation, snapshot]),
        add=MagicMock(),
        add_all=MagicMock(),
        flush=AsyncMock(),
    )
    store = SqlAlchemyKnowledgeStore(session, WORKSPACE_ID)

    result = await store.create_pipeline_chunk(
        CreatePipelineChunkCommand(
            generation_id=GENERATION_ID,
            ordinal=1,
            text="Governed source text",
            locator={"section": "overview", "paragraph": 1},
            locale="en",
            topics=("product",),
            audiences=("sales",),
            untrusted_content_flags=("instruction_like_text",),
        ),
        KnowledgeMutationContext(
            actor_type="service",
            actor_id="knowledge-worker",
            session_id=None,
            request_id="request-pipeline",
            idempotency_key="chunk-generation-1-ordinal-1",
        ),
    )

    assert result.idempotent_replay is False
    assert result.chunk.source_type == "pipeline"
    assert result.chunk.status == "draft"
    assert result.chunk.payload["sourceVersionId"] == str(SOURCE_VERSION_ID)
    assert result.chunk.payload["untrustedContentFlags"] == ["instruction_like_text"]
    assert generation.status == "building"
    assert generation.chunk_count == 1

    singly_added = [call.args[0] for call in session.add.call_args_list]
    added = [*singly_added, *session.add_all.call_args.args[0]]
    assert any(
        isinstance(item, BusinessObject) and item.object_type == "knowledge_chunk"
        for item in added
    )
    assert any(
        isinstance(item, BusinessObjectVersion) and item.source_type == "pipeline"
        for item in added
    )
    assert any(isinstance(item, KnowledgeGenerationChunk) for item in added)
    assert any(
        isinstance(item, AuditEvent) and item.action == "knowledge.chunk_created"
        for item in added
    )
    assert any(
        isinstance(item, OutboxEvent) and item.event_type == "KnowledgeChunkCreated"
        for item in added
    )
