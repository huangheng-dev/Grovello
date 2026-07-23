from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from grovello.access import AuthorizedWorkspace
from grovello.api.dependencies import (
    get_knowledge_store,
    require_idempotency_key,
    require_workspace_access,
)
from grovello.knowledge import (
    CreateKnowledgeIngestionCommand,
    KnowledgeConflictError,
    KnowledgeIngestionRecord,
    KnowledgeMutationContext,
    KnowledgeNotFoundError,
    KnowledgeStore,
)
from grovello.schemas import (
    ApiEnvelope,
    ApiMeta,
    KnowledgeGenerationSummary,
    KnowledgeIngestionCreate,
    KnowledgeIngestionListSummary,
    KnowledgeIngestionMutationSummary,
    KnowledgeIngestionSummary,
    KnowledgeSourceSnapshotSummary,
)

router = APIRouter()


def _raise_store_error(error: Exception) -> NoReturn:
    if isinstance(error, KnowledgeNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    if isinstance(error, KnowledgeConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    raise error


def _summary(record: KnowledgeIngestionRecord) -> KnowledgeIngestionSummary:
    return KnowledgeIngestionSummary(
        id=record.id,
        workspace_id=record.workspace_id,
        source_object_id=record.source_object_id,
        source_version_id=record.source_version_id,
        source_object_type=record.source_object_type,
        actor_id=record.actor_id,
        business_purpose=record.business_purpose,
        pipeline_profile=record.pipeline_profile,
        pipeline_version=record.pipeline_version,
        status=record.status,
        input_versions=record.input_versions,
        approval_policy_version=record.approval_policy_version,
        workflow_id=record.workflow_id,
        workflow_run_id=record.workflow_run_id,
        cost_summary=record.cost_summary,
        failure_code=record.failure_code,
        failure_detail=record.failure_detail,
        created_at=record.created_at,
        updated_at=record.updated_at,
        snapshot=KnowledgeSourceSnapshotSummary(
            id=record.snapshot.id,
            source_object_id=record.snapshot.source_object_id,
            source_version_id=record.snapshot.source_version_id,
            source_object_type=record.snapshot.source_object_type,
            content_sha256=record.snapshot.content_sha256,
            locale=record.snapshot.locale,
            source_status=record.snapshot.source_status,
            usage_rights=record.snapshot.usage_rights,
            sensitivity=record.snapshot.sensitivity,
            parser_eligible=record.snapshot.parser_eligible,
            source_locator=record.snapshot.source_locator,
            source_metadata=record.snapshot.source_metadata,
            policy_version=record.snapshot.policy_version,
            created_at=record.snapshot.created_at,
        ),
        generation=KnowledgeGenerationSummary(
            id=record.generation.id,
            status=record.generation.status,
            pipeline_profile=record.generation.pipeline_profile,
            pipeline_version=record.generation.pipeline_version,
            parser_profile=record.generation.parser_profile,
            normalizer_version=record.generation.normalizer_version,
            classifier_version=record.generation.classifier_version,
            chunker_version=record.generation.chunker_version,
            embedding_config=record.generation.embedding_config,
            chunk_count=record.generation.chunk_count,
            warnings=record.generation.warnings,
            created_at=record.generation.created_at,
            updated_at=record.generation.updated_at,
        ),
    )


@router.post(
    "/ingestions",
    response_model=ApiEnvelope[KnowledgeIngestionMutationSummary],
    status_code=status.HTTP_201_CREATED,
)
async def create_knowledge_ingestion(
    payload: KnowledgeIngestionCreate,
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[KnowledgeStore, Depends(get_knowledge_store)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> ApiEnvelope[KnowledgeIngestionMutationSummary]:
    access.require("knowledge.ingest")
    try:
        result = await store.create_ingestion(
            CreateKnowledgeIngestionCommand(
                source_object_id=payload.source_object_id,
                source_version_id=payload.source_version_id,
                business_purpose=payload.business_purpose,
                pipeline_profile=payload.pipeline_profile,
                pipeline_version=payload.pipeline_version,
                input_versions=payload.input_versions,
                approval_policy_version=payload.approval_policy_version,
            ),
            KnowledgeMutationContext(
                actor_type=access.actor.actor_type,
                actor_id=access.actor.subject_id,
                session_id=access.actor.session_id,
                request_id=request.state.request_id,
                idempotency_key=idempotency_key,
            ),
        )
    except (KnowledgeNotFoundError, KnowledgeConflictError) as error:
        _raise_store_error(error)
    return ApiEnvelope(
        data=KnowledgeIngestionMutationSummary(
            ingestion=_summary(result.ingestion),
            idempotent_replay=result.idempotent_replay,
        ),
        meta=ApiMeta(request_id=request.state.request_id),
    )


@router.get(
    "/ingestions",
    response_model=ApiEnvelope[KnowledgeIngestionListSummary],
)
async def list_knowledge_ingestions(
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[KnowledgeStore, Depends(get_knowledge_store)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiEnvelope[KnowledgeIngestionListSummary]:
    access.require("knowledge.retrieve")
    records = await store.list_ingestions(limit)
    return ApiEnvelope(
        data=KnowledgeIngestionListSummary(items=[_summary(record) for record in records]),
        meta=ApiMeta(request_id=request.state.request_id),
    )


@router.get(
    "/ingestions/{ingestion_id}",
    response_model=ApiEnvelope[KnowledgeIngestionSummary],
)
async def get_knowledge_ingestion(
    ingestion_id: UUID,
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[KnowledgeStore, Depends(get_knowledge_store)],
) -> ApiEnvelope[KnowledgeIngestionSummary]:
    access.require("knowledge.retrieve")
    try:
        record = await store.get_ingestion(ingestion_id)
    except (KnowledgeNotFoundError, KnowledgeConflictError) as error:
        _raise_store_error(error)
    return ApiEnvelope(
        data=_summary(record),
        meta=ApiMeta(request_id=request.state.request_id),
    )
