import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from grovello.models import (
    AssetBlob,
    AssetVersionFile,
    AuditEvent,
    BusinessObject,
    BusinessObjectVersion,
    KnowledgeGeneration,
    KnowledgeGenerationChunk,
    KnowledgeIngestion,
    KnowledgeSourceSnapshot,
    OutboxEvent,
)

type KnowledgeSourceType = Literal["knowledge_document", "evidence", "case_study", "asset"]
type KnowledgeIngestionStatus = Literal["pending", "running", "ready", "failed", "cancelled"]
type KnowledgeGenerationStatus = Literal[
    "pending", "building", "staged", "active", "retired", "failed"
]

ALLOWED_SOURCE_TYPES: frozenset[KnowledgeSourceType] = frozenset(
    {"knowledge_document", "evidence", "case_study", "asset"}
)
PIPELINE_ACTOR_TYPE = "service"
PIPELINE_CHUNK_MAX_CHARACTERS = 16_384


class KnowledgeNotFoundError(LookupError):
    pass


class KnowledgeConflictError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class KnowledgeMutationContext:
    actor_type: str
    actor_id: str
    session_id: str | None
    request_id: str | None
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class CreateKnowledgeIngestionCommand:
    source_object_id: UUID
    source_version_id: UUID
    business_purpose: str
    pipeline_profile: str
    pipeline_version: str
    input_versions: dict
    approval_policy_version: int | None


@dataclass(frozen=True, slots=True)
class KnowledgeSourceSnapshotRecord:
    id: UUID
    source_object_id: UUID
    source_version_id: UUID
    source_object_type: KnowledgeSourceType
    content_sha256: str
    locale: str
    source_status: str
    usage_rights: str
    sensitivity: str
    parser_eligible: bool
    source_locator: dict
    source_metadata: dict
    policy_version: int | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class KnowledgeGenerationRecord:
    id: UUID
    status: KnowledgeGenerationStatus
    pipeline_profile: str
    pipeline_version: str
    parser_profile: str
    normalizer_version: str
    classifier_version: str
    chunker_version: str
    embedding_config: dict
    chunk_count: int
    warnings: list
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class KnowledgeIngestionRecord:
    id: UUID
    workspace_id: UUID
    source_object_id: UUID
    source_version_id: UUID
    source_object_type: KnowledgeSourceType
    actor_id: str
    business_purpose: str
    pipeline_profile: str
    pipeline_version: str
    status: KnowledgeIngestionStatus
    input_versions: dict
    approval_policy_version: int | None
    workflow_id: str | None
    workflow_run_id: str | None
    cost_summary: dict
    failure_code: str | None
    failure_detail: str | None
    created_at: datetime
    updated_at: datetime
    snapshot: KnowledgeSourceSnapshotRecord
    generation: KnowledgeGenerationRecord


@dataclass(frozen=True, slots=True)
class KnowledgeIngestionMutationResult:
    ingestion: KnowledgeIngestionRecord
    idempotent_replay: bool


@dataclass(frozen=True, slots=True)
class CreatePipelineChunkCommand:
    generation_id: UUID
    ordinal: int
    text: str
    locator: dict
    locale: str
    topics: tuple[str, ...] = ()
    audiences: tuple[str, ...] = ()
    usage_rights: str = "internal_only"
    sensitivity: str = "internal"
    untrusted_content_flags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PipelineChunkRecord:
    object_id: UUID
    version_id: UUID
    generation_id: UUID
    ordinal: int
    content_sha256: str
    slug: str
    status: str
    source_type: str
    payload: dict


@dataclass(frozen=True, slots=True)
class PipelineChunkMutationResult:
    chunk: PipelineChunkRecord
    idempotent_replay: bool


class KnowledgeStore(Protocol):
    async def create_ingestion(
        self,
        command: CreateKnowledgeIngestionCommand,
        context: KnowledgeMutationContext,
    ) -> KnowledgeIngestionMutationResult: ...

    async def list_ingestions(self, limit: int) -> tuple[KnowledgeIngestionRecord, ...]: ...

    async def get_ingestion(self, ingestion_id: UUID) -> KnowledgeIngestionRecord: ...


class SqlAlchemyKnowledgeStore:
    def __init__(self, session: AsyncSession, workspace_id: UUID) -> None:
        self._session = session
        self._workspace_id = workspace_id

    async def create_ingestion(
        self,
        command: CreateKnowledgeIngestionCommand,
        context: KnowledgeMutationContext,
    ) -> KnowledgeIngestionMutationResult:
        request_hash = _request_hash(command)
        replay = await self._session.scalar(
            select(KnowledgeIngestion).where(
                KnowledgeIngestion.workspace_id == self._workspace_id,
                KnowledgeIngestion.idempotency_key == context.idempotency_key,
            )
        )
        if replay is not None:
            if replay.request_hash != request_hash:
                raise KnowledgeConflictError(
                    "Idempotency key was already used for a different knowledge ingestion"
                )
            return KnowledgeIngestionMutationResult(
                ingestion=await self.get_ingestion(replay.id),
                idempotent_replay=True,
            )

        source_object, source_version = await self._eligible_source(command)
        snapshot_data = await self._snapshot_data(source_object, source_version)
        ingestion_id = uuid.uuid4()
        snapshot_id = uuid.uuid4()
        generation_id = uuid.uuid4()
        ingestion = KnowledgeIngestion(
            id=ingestion_id,
            workspace_id=self._workspace_id,
            source_object_id=source_object.id,
            source_version_id=source_version.id,
            source_object_type=source_object.object_type,
            actor_id=context.actor_id,
            session_id=context.session_id,
            request_id=context.request_id,
            idempotency_key=context.idempotency_key,
            request_hash=request_hash,
            business_purpose=command.business_purpose,
            pipeline_profile=command.pipeline_profile,
            pipeline_version=command.pipeline_version,
            status="pending",
            input_versions=command.input_versions,
            approval_policy_version=command.approval_policy_version,
            cost_summary={},
        )
        snapshot = KnowledgeSourceSnapshot(
            id=snapshot_id,
            workspace_id=self._workspace_id,
            ingestion_id=ingestion_id,
            source_object_id=source_object.id,
            source_version_id=source_version.id,
            source_object_type=source_object.object_type,
            content_sha256=snapshot_data["content_sha256"],
            locale=source_version.locale,
            source_status=source_version.status,
            usage_rights=snapshot_data["usage_rights"],
            sensitivity=snapshot_data["sensitivity"],
            parser_eligible=snapshot_data["parser_eligible"],
            source_locator=snapshot_data["source_locator"],
            source_metadata=snapshot_data["source_metadata"],
            policy_version=command.approval_policy_version,
        )
        generation = KnowledgeGeneration(
            id=generation_id,
            workspace_id=self._workspace_id,
            ingestion_id=ingestion_id,
            source_snapshot_id=snapshot_id,
            status="pending",
            pipeline_profile=command.pipeline_profile,
            pipeline_version=command.pipeline_version,
            parser_profile="canonical-json-v1",
            normalizer_version="none",
            classifier_version="none",
            chunker_version="none",
            embedding_config={},
            chunk_count=0,
            warnings=[],
        )
        audit = AuditEvent(
            id=uuid.uuid4(),
            workspace_id=self._workspace_id,
            actor_type=context.actor_type,
            actor_id=context.actor_id,
            session_id=context.session_id,
            request_id=context.request_id,
            action="knowledge.ingestion_created",
            resource_type="KnowledgeIngestion",
            resource_id=str(ingestion_id),
            outcome="succeeded",
            reason=command.business_purpose,
            evidence={
                "sourceObjectId": str(source_object.id),
                "sourceVersionId": str(source_version.id),
                "sourceObjectType": source_object.object_type,
                "contentSha256": snapshot_data["content_sha256"],
                "pipelineProfile": command.pipeline_profile,
                "pipelineVersion": command.pipeline_version,
                "idempotencyKey": context.idempotency_key,
            },
        )
        outbox = OutboxEvent(
            id=uuid.uuid4(),
            workspace_id=self._workspace_id,
            aggregate_type="KnowledgeIngestion",
            aggregate_id=str(ingestion_id),
            event_type="KnowledgeIngestionCreated",
            event_version=1,
            payload={
                "ingestionId": str(ingestion_id),
                "sourceObjectId": str(source_object.id),
                "sourceVersionId": str(source_version.id),
                "sourceObjectType": source_object.object_type,
                "generationId": str(generation_id),
                "pipelineProfile": command.pipeline_profile,
                "pipelineVersion": command.pipeline_version,
            },
        )
        self._session.add(ingestion)
        await self._session.flush()
        self._session.add(snapshot)
        await self._session.flush()
        self._session.add_all([generation, audit, outbox])
        await self._session.flush()
        return KnowledgeIngestionMutationResult(
            ingestion=await self.get_ingestion(ingestion_id),
            idempotent_replay=False,
        )

    async def list_ingestions(self, limit: int) -> tuple[KnowledgeIngestionRecord, ...]:
        ingestions = list(
            await self._session.scalars(
                select(KnowledgeIngestion)
                .where(KnowledgeIngestion.workspace_id == self._workspace_id)
                .order_by(KnowledgeIngestion.created_at.desc(), KnowledgeIngestion.id)
                .limit(limit)
            )
        )
        return tuple([await self.get_ingestion(ingestion.id) for ingestion in ingestions])

    async def get_ingestion(self, ingestion_id: UUID) -> KnowledgeIngestionRecord:
        ingestion = await self._session.scalar(
            select(KnowledgeIngestion).where(
                KnowledgeIngestion.workspace_id == self._workspace_id,
                KnowledgeIngestion.id == ingestion_id,
            )
        )
        if ingestion is None:
            raise KnowledgeNotFoundError("Knowledge ingestion was not found")
        snapshot = await self._session.scalar(
            select(KnowledgeSourceSnapshot).where(
                KnowledgeSourceSnapshot.workspace_id == self._workspace_id,
                KnowledgeSourceSnapshot.ingestion_id == ingestion.id,
            )
        )
        generation = await self._session.scalar(
            select(KnowledgeGeneration).where(
                KnowledgeGeneration.workspace_id == self._workspace_id,
                KnowledgeGeneration.ingestion_id == ingestion.id,
            )
        )
        if snapshot is None or generation is None:
            raise KnowledgeConflictError("Knowledge ingestion lineage is incomplete")
        return _ingestion_record(ingestion, snapshot, generation)

    async def create_pipeline_chunk(
        self,
        command: CreatePipelineChunkCommand,
        context: KnowledgeMutationContext,
    ) -> PipelineChunkMutationResult:
        if context.actor_type != PIPELINE_ACTOR_TYPE:
            raise KnowledgeConflictError("Knowledge chunks can only be created by a pipeline service")
        _validate_chunk(command)
        replay_version = await self._session.scalar(
            select(BusinessObjectVersion).where(
                BusinessObjectVersion.workspace_id == self._workspace_id,
                BusinessObjectVersion.idempotency_key == context.idempotency_key,
            )
        )
        if replay_version is not None:
            replay_object = await self._session.scalar(
                select(BusinessObject).where(
                    BusinessObject.workspace_id == self._workspace_id,
                    BusinessObject.id == replay_version.object_id,
                    BusinessObject.object_type == "knowledge_chunk",
                )
            )
            replay_link = await self._session.scalar(
                select(KnowledgeGenerationChunk).where(
                    KnowledgeGenerationChunk.workspace_id == self._workspace_id,
                    KnowledgeGenerationChunk.chunk_version_id == replay_version.id,
                )
            )
            if (
                replay_object is None
                or replay_link is None
                or replay_version.source_type != "pipeline"
                or replay_link.generation_id != command.generation_id
                or replay_link.ordinal != command.ordinal
            ):
                raise KnowledgeConflictError(
                    "Idempotency key belongs to another pipeline operation"
                )
            return PipelineChunkMutationResult(
                chunk=_chunk_record(replay_object, replay_version, replay_link),
                idempotent_replay=True,
            )

        generation = await self._session.scalar(
            select(KnowledgeGeneration)
            .where(
                KnowledgeGeneration.workspace_id == self._workspace_id,
                KnowledgeGeneration.id == command.generation_id,
            )
            .with_for_update()
        )
        if generation is None:
            raise KnowledgeNotFoundError("Knowledge generation was not found")
        if generation.status not in {"pending", "building"}:
            raise KnowledgeConflictError("Knowledge generation is not accepting chunks")
        snapshot = await self._session.scalar(
            select(KnowledgeSourceSnapshot).where(
                KnowledgeSourceSnapshot.workspace_id == self._workspace_id,
                KnowledgeSourceSnapshot.id == generation.source_snapshot_id,
            )
        )
        if snapshot is None:
            raise KnowledgeConflictError("Knowledge generation source snapshot is unavailable")

        content_sha256 = hashlib.sha256(command.text.encode("utf-8")).hexdigest()
        object_id = uuid.uuid4()
        version_id = uuid.uuid4()
        slug = (
            f"chunk-{generation.id.hex[:12]}-{command.ordinal}-{content_sha256[:12]}"
        )
        payload = {
            "text": command.text,
            "ordinal": command.ordinal,
            "sourceLocator": command.locator,
            "contentSha256": content_sha256,
            "locale": command.locale,
            "characterCount": len(command.text),
            "topics": list(command.topics),
            "audiences": list(command.audiences),
            "usageRights": command.usage_rights,
            "sensitivity": command.sensitivity,
            "untrustedContentFlags": list(command.untrusted_content_flags),
            "generationId": str(generation.id),
            "sourceObjectId": str(snapshot.source_object_id),
            "sourceVersionId": str(snapshot.source_version_id),
            "pipelineProfile": generation.pipeline_profile,
            "pipelineVersion": generation.pipeline_version,
        }
        chunk_object = BusinessObject(
            id=object_id,
            workspace_id=self._workspace_id,
            object_type="knowledge_chunk",
            slug=slug,
            name=f"Knowledge chunk {command.ordinal}",
            status="draft",
            current_version=1,
        )
        chunk_version = BusinessObjectVersion(
            id=version_id,
            workspace_id=self._workspace_id,
            object_id=object_id,
            version=1,
            schema_version=1,
            name=f"Knowledge chunk {command.ordinal}",
            status="draft",
            locale=command.locale,
            payload=payload,
            business_purpose="Build a governed knowledge retrieval generation",
            actor_id=context.actor_id,
            idempotency_key=context.idempotency_key,
            source_type="pipeline",
            source_ref=f"knowledge-generation:{generation.id}",
            change_summary="Create an immutable pipeline-derived knowledge chunk",
            input_versions={
                "ingestionId": str(generation.ingestion_id),
                "generationId": str(generation.id),
                "sourceObjectId": str(snapshot.source_object_id),
                "sourceVersionId": str(snapshot.source_version_id),
                "pipelineProfile": generation.pipeline_profile,
                "pipelineVersion": generation.pipeline_version,
            },
        )
        link = KnowledgeGenerationChunk(
            id=uuid.uuid4(),
            workspace_id=self._workspace_id,
            generation_id=generation.id,
            chunk_object_id=object_id,
            chunk_version_id=version_id,
            ordinal=command.ordinal,
            content_sha256=content_sha256,
        )
        generation.status = "building"
        generation.chunk_count += 1
        audit = AuditEvent(
            id=uuid.uuid4(),
            workspace_id=self._workspace_id,
            actor_type=context.actor_type,
            actor_id=context.actor_id,
            session_id=context.session_id,
            request_id=context.request_id,
            action="knowledge.chunk_created",
            resource_type="KnowledgeChunk",
            resource_id=str(object_id),
            outcome="succeeded",
            reason="Build a governed knowledge retrieval generation",
            evidence={
                "ingestionId": str(generation.ingestion_id),
                "generationId": str(generation.id),
                "sourceVersionId": str(snapshot.source_version_id),
                "chunkVersionId": str(version_id),
                "ordinal": command.ordinal,
                "contentSha256": content_sha256,
                "idempotencyKey": context.idempotency_key,
            },
        )
        outbox = OutboxEvent(
            id=uuid.uuid4(),
            workspace_id=self._workspace_id,
            aggregate_type="KnowledgeChunk",
            aggregate_id=str(object_id),
            event_type="KnowledgeChunkCreated",
            event_version=1,
            payload={
                "chunkObjectId": str(object_id),
                "chunkVersionId": str(version_id),
                "generationId": str(generation.id),
                "sourceVersionId": str(snapshot.source_version_id),
                "ordinal": command.ordinal,
                "contentSha256": content_sha256,
            },
        )
        self._session.add(chunk_object)
        await self._session.flush()
        self._session.add(chunk_version)
        await self._session.flush()
        self._session.add_all([link, audit, outbox])
        await self._session.flush()
        return PipelineChunkMutationResult(
            chunk=_chunk_record(chunk_object, chunk_version, link),
            idempotent_replay=False,
        )

    async def _eligible_source(
        self,
        command: CreateKnowledgeIngestionCommand,
    ) -> tuple[BusinessObject, BusinessObjectVersion]:
        row = (
            await self._session.execute(
                select(BusinessObject, BusinessObjectVersion)
                .join(
                    BusinessObjectVersion,
                    and_(
                        BusinessObjectVersion.workspace_id == BusinessObject.workspace_id,
                        BusinessObjectVersion.object_id == BusinessObject.id,
                    ),
                )
                .where(
                    BusinessObject.workspace_id == self._workspace_id,
                    BusinessObject.id == command.source_object_id,
                    BusinessObjectVersion.id == command.source_version_id,
                )
            )
        ).one_or_none()
        if row is None:
            raise KnowledgeNotFoundError("Knowledge source version was not found")
        source_object, source_version = row
        if source_object.object_type not in ALLOWED_SOURCE_TYPES:
            raise KnowledgeConflictError("Business object type is not an eligible knowledge source")
        if source_object.status != "active" or source_version.status != "active":
            raise KnowledgeConflictError("Knowledge source version must be active")
        if (
            source_object.object_type == "knowledge_document"
            and source_version.payload.get("knowledgeStatus") != "approved"
        ):
            raise KnowledgeConflictError("Knowledge document must be approved before ingestion")
        if source_object.object_type == "evidence" and source_version.payload.get(
            "verificationStatus"
        ) not in {"verified", "owner_attested"}:
            raise KnowledgeConflictError(
                "Evidence must be verified or owner-attested before ingestion"
            )
        return source_object, source_version

    async def _snapshot_data(
        self,
        source_object: BusinessObject,
        source_version: BusinessObjectVersion,
    ) -> dict:
        payload = source_version.payload
        usage_rights = str(payload.get("usageRights") or "internal_only")
        sensitivity = str(payload.get("sensitivity") or "internal")
        source_locator: dict = {
            "sourceObjectId": str(source_object.id),
            "sourceVersionId": str(source_version.id),
        }
        source_metadata: dict = {
            "objectType": source_object.object_type,
            "objectSlug": source_object.slug,
            "objectVersion": source_version.version,
            "schemaVersion": source_version.schema_version,
        }
        parser_eligible = True
        if source_object.object_type == "asset":
            file_row = (
                await self._session.execute(
                    select(AssetVersionFile, AssetBlob)
                    .join(
                        AssetBlob,
                        and_(
                            AssetBlob.workspace_id == AssetVersionFile.workspace_id,
                            AssetBlob.id == AssetVersionFile.blob_id,
                        ),
                    )
                    .where(
                        AssetVersionFile.workspace_id == self._workspace_id,
                        AssetVersionFile.business_object_version_id == source_version.id,
                        AssetVersionFile.role == "original",
                        AssetVersionFile.variant_key == "default",
                    )
                )
            ).one_or_none()
            if file_row is None:
                raise KnowledgeConflictError("Asset knowledge source has no exact original file")
            _binding, blob = file_row
            if blob.scan_status != "clean" or blob.storage_status != "available":
                raise KnowledgeConflictError(
                    "Asset knowledge source must be clean and available"
                )
            parser_eligible = blob.detected_mime_type in {
                "text/plain",
                "text/markdown",
            }
            if not parser_eligible:
                raise KnowledgeConflictError(
                    "Asset type is not eligible for the P2-E1 canonical text profile"
                )
            content_sha256 = blob.sha256
            source_locator["blobId"] = str(blob.id)
            source_metadata.update(
                {
                    "byteSize": blob.byte_size,
                    "detectedMimeType": blob.detected_mime_type,
                    "scanStatus": blob.scan_status,
                    "storageStatus": blob.storage_status,
                }
            )
        else:
            content_sha256 = hashlib.sha256(
                _stable_json(
                    {
                        "sourceObjectId": str(source_object.id),
                        "sourceVersionId": str(source_version.id),
                        "locale": source_version.locale,
                        "payload": payload,
                    }
                ).encode("utf-8")
            ).hexdigest()
        return {
            "content_sha256": content_sha256,
            "usage_rights": usage_rights,
            "sensitivity": sensitivity,
            "parser_eligible": parser_eligible,
            "source_locator": source_locator,
            "source_metadata": source_metadata,
        }


def _request_hash(command: CreateKnowledgeIngestionCommand) -> str:
    return hashlib.sha256(
        _stable_json(
            {
                "sourceObjectId": str(command.source_object_id),
                "sourceVersionId": str(command.source_version_id),
                "businessPurpose": command.business_purpose,
                "pipelineProfile": command.pipeline_profile,
                "pipelineVersion": command.pipeline_version,
                "inputVersions": command.input_versions,
                "approvalPolicyVersion": command.approval_policy_version,
            }
        ).encode("utf-8")
    ).hexdigest()


def _stable_json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _validate_chunk(command: CreatePipelineChunkCommand) -> None:
    if command.ordinal <= 0:
        raise KnowledgeConflictError("Knowledge chunk ordinal must be positive")
    if not command.text.strip():
        raise KnowledgeConflictError("Knowledge chunk text is required")
    if len(command.text) > PIPELINE_CHUNK_MAX_CHARACTERS:
        raise KnowledgeConflictError("Knowledge chunk text exceeds the P2-E1 safety limit")
    if not command.locator:
        raise KnowledgeConflictError("Knowledge chunk requires an exact source locator")
    if not 2 <= len(command.locale) <= 12:
        raise KnowledgeConflictError("Knowledge chunk locale is invalid")


def _ingestion_record(
    ingestion: KnowledgeIngestion,
    snapshot: KnowledgeSourceSnapshot,
    generation: KnowledgeGeneration,
) -> KnowledgeIngestionRecord:
    return KnowledgeIngestionRecord(
        id=ingestion.id,
        workspace_id=ingestion.workspace_id,
        source_object_id=ingestion.source_object_id,
        source_version_id=ingestion.source_version_id,
        source_object_type=ingestion.source_object_type,
        actor_id=ingestion.actor_id,
        business_purpose=ingestion.business_purpose,
        pipeline_profile=ingestion.pipeline_profile,
        pipeline_version=ingestion.pipeline_version,
        status=ingestion.status,
        input_versions=ingestion.input_versions,
        approval_policy_version=ingestion.approval_policy_version,
        workflow_id=ingestion.workflow_id,
        workflow_run_id=ingestion.workflow_run_id,
        cost_summary=ingestion.cost_summary,
        failure_code=ingestion.failure_code,
        failure_detail=ingestion.failure_detail,
        created_at=ingestion.created_at,
        updated_at=ingestion.updated_at,
        snapshot=KnowledgeSourceSnapshotRecord(
            id=snapshot.id,
            source_object_id=snapshot.source_object_id,
            source_version_id=snapshot.source_version_id,
            source_object_type=snapshot.source_object_type,
            content_sha256=snapshot.content_sha256,
            locale=snapshot.locale,
            source_status=snapshot.source_status,
            usage_rights=snapshot.usage_rights,
            sensitivity=snapshot.sensitivity,
            parser_eligible=snapshot.parser_eligible,
            source_locator=snapshot.source_locator,
            source_metadata=snapshot.source_metadata,
            policy_version=snapshot.policy_version,
            created_at=snapshot.created_at,
        ),
        generation=KnowledgeGenerationRecord(
            id=generation.id,
            status=generation.status,
            pipeline_profile=generation.pipeline_profile,
            pipeline_version=generation.pipeline_version,
            parser_profile=generation.parser_profile,
            normalizer_version=generation.normalizer_version,
            classifier_version=generation.classifier_version,
            chunker_version=generation.chunker_version,
            embedding_config=generation.embedding_config,
            chunk_count=generation.chunk_count,
            warnings=generation.warnings,
            created_at=generation.created_at,
            updated_at=generation.updated_at,
        ),
    )


def _chunk_record(
    chunk_object: BusinessObject,
    chunk_version: BusinessObjectVersion,
    link: KnowledgeGenerationChunk,
) -> PipelineChunkRecord:
    return PipelineChunkRecord(
        object_id=chunk_object.id,
        version_id=chunk_version.id,
        generation_id=link.generation_id,
        ordinal=link.ordinal,
        content_sha256=link.content_sha256,
        slug=chunk_object.slug,
        status=chunk_version.status,
        source_type=chunk_version.source_type,
        payload=chunk_version.payload,
    )
