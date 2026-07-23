import asyncio
from uuid import UUID

from sqlalchemy import func, select

from grovello.business_truth import BusinessTruthNotFoundError, SqlAlchemyBusinessTruthStore
from grovello.database import workspace_session
from grovello.knowledge import (
    CreatePipelineChunkCommand,
    KnowledgeMutationContext,
    SqlAlchemyKnowledgeStore,
)
from grovello.models import (
    AuditEvent,
    KnowledgeGeneration,
    KnowledgeGenerationChunk,
    OutboxEvent,
)

WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000001")


async def main() -> None:
    async with workspace_session(WORKSPACE_ID) as session:
        generation = await session.scalar(
            select(KnowledgeGeneration)
            .where(KnowledgeGeneration.workspace_id == WORKSPACE_ID)
            .order_by(KnowledgeGeneration.created_at.desc())
            .limit(1)
        )
        assert generation is not None
        store = SqlAlchemyKnowledgeStore(session, WORKSPACE_ID)
        context = KnowledgeMutationContext(
            actor_type="service",
            actor_id="knowledge-worker",
            session_id=None,
            request_id="p2-e1-pipeline-integration",
            idempotency_key=f"p2-e1-chunk-{generation.id}-1",
        )
        command = CreatePipelineChunkCommand(
            generation_id=generation.id,
            ordinal=1,
            text=(
                "Grovello keeps pipeline-derived knowledge chunks isolated and exactly "
                "traceable to one approved source version."
            ),
            locator={"section": "acceptance", "paragraph": 1},
            locale="en",
            topics=("knowledge governance",),
            audiences=("product operations",),
            usage_rights="internal_only",
            sensitivity="internal",
            untrusted_content_flags=(),
        )

        first = await store.create_pipeline_chunk(command, context)
        replay = await store.create_pipeline_chunk(command, context)

        assert first.idempotent_replay is False
        assert replay.idempotent_replay is True
        assert replay.chunk.version_id == first.chunk.version_id
        assert first.chunk.source_type == "pipeline"
        assert first.chunk.status == "draft"

        chunk_count = await session.scalar(
            select(func.count())
            .select_from(KnowledgeGenerationChunk)
            .where(
                KnowledgeGenerationChunk.workspace_id == WORKSPACE_ID,
                KnowledgeGenerationChunk.generation_id == generation.id,
            )
        )
        audit_count = await session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.workspace_id == WORKSPACE_ID,
                AuditEvent.action == "knowledge.chunk_created",
                AuditEvent.resource_id == str(first.chunk.object_id),
            )
        )
        outbox_count = await session.scalar(
            select(func.count())
            .select_from(OutboxEvent)
            .where(
                OutboxEvent.workspace_id == WORKSPACE_ID,
                OutboxEvent.event_type == "KnowledgeChunkCreated",
                OutboxEvent.aggregate_id == str(first.chunk.object_id),
            )
        )
        assert chunk_count == 1
        assert audit_count == 1
        assert outbox_count == 1

        truth = SqlAlchemyBusinessTruthStore(session, WORKSPACE_ID)
        profile = await truth.get_profile()
        assert all(item.object_type != "knowledge_chunk" for item in profile.objects)
        try:
            await truth.get_object(first.chunk.object_id)
        except BusinessTruthNotFoundError:
            pass
        else:
            raise AssertionError("Pipeline chunks must not be exposed by generic business truth")

        print(
            "P2-E1 integration passed:",
            {
                "generationId": str(generation.id),
                "chunkObjectId": str(first.chunk.object_id),
                "chunkVersionId": str(first.chunk.version_id),
                "chunkCount": chunk_count,
                "auditCount": audit_count,
                "outboxCount": outbox_count,
            },
        )


if __name__ == "__main__":
    asyncio.run(main())
