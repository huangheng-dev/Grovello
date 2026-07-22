from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from grovello.access import AuthorizedWorkspace
from grovello.api.dependencies import (
    get_business_truth_store,
    require_idempotency_key,
    require_workspace_access,
)
from grovello.business_truth import (
    BusinessObjectRecord,
    BusinessProfileRecord,
    BusinessTruthConflictError,
    BusinessTruthMutationResult,
    BusinessTruthNotFoundError,
    BusinessTruthStore,
    CitationDraft,
    CreateBusinessObjectCommand,
    CreateBusinessObjectVersionCommand,
    InvalidBusinessTruthPayloadError,
    InvalidEvidenceCitationError,
    MutationContext,
)
from grovello.schemas import (
    ApiEnvelope,
    ApiMeta,
    BusinessObjectCreate,
    BusinessObjectSummary,
    BusinessObjectVersionCreate,
    BusinessObjectVersionSummary,
    BusinessProfileSummary,
    BusinessTruthCitationSummary,
    BusinessTruthMutationSummary,
)

router = APIRouter()


def citation_drafts(items) -> tuple[CitationDraft, ...]:
    return tuple(
        CitationDraft(
            evidence_version_id=item.evidence_version_id,
            claim_text=item.claim_text,
            locator=item.locator,
        )
        for item in items
    )


def object_summary(record: BusinessObjectRecord) -> BusinessObjectSummary:
    version = record.version
    return BusinessObjectSummary(
        id=str(record.id),
        workspace_id=str(record.workspace_id),
        object_type=record.object_type,
        slug=record.slug,
        current_version=record.current_version,
        version=BusinessObjectVersionSummary(
            id=str(version.id),
            version=version.version,
            schema_version=version.schema_version,
            name=version.name,
            status=version.status,
            locale=version.locale,
            payload=version.payload,
            business_purpose=version.business_purpose,
            actor_id=version.actor_id,
            source_type=version.source_type,
            source_ref=version.source_ref,
            change_summary=version.change_summary,
            input_versions=version.input_versions,
            created_at=version.created_at,
            citations=[
                BusinessTruthCitationSummary(
                    id=str(citation.id),
                    evidence_object_id=str(citation.evidence_object_id),
                    evidence_version_id=str(citation.evidence_version_id),
                    evidence_version=citation.evidence_version,
                    evidence_name=citation.evidence_name,
                    claim_text=citation.claim_text,
                    locator=citation.locator,
                )
                for citation in version.citations
            ],
        ),
    )


def profile_summary(profile: BusinessProfileRecord) -> BusinessProfileSummary:
    return BusinessProfileSummary(
        workspace_id=str(profile.workspace_id),
        validation_state="complete" if profile.is_complete else "incomplete",
        object_count=len(profile.objects),
        citation_count=profile.citation_count,
        missing_object_types=list(profile.missing_object_types),
        objects=[object_summary(item) for item in profile.objects],
    )


def mutation_summary(result: BusinessTruthMutationResult) -> BusinessTruthMutationSummary:
    return BusinessTruthMutationSummary(
        object=object_summary(result.object),
        idempotent_replay=result.idempotent_replay,
    )


def raise_store_error(error: Exception) -> NoReturn:
    if isinstance(error, BusinessTruthNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    if isinstance(error, BusinessTruthConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    if isinstance(error, InvalidEvidenceCitationError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    if isinstance(error, InvalidBusinessTruthPayloadError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    raise error


@router.get("/profile", response_model=ApiEnvelope[BusinessProfileSummary])
async def get_business_profile(
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[BusinessTruthStore, Depends(get_business_truth_store)],
) -> ApiEnvelope[BusinessProfileSummary]:
    access.require("business_truth.read")
    profile = await store.get_profile()
    return ApiEnvelope(
        data=profile_summary(profile),
        meta=ApiMeta(request_id=request.state.request_id, source=store.source),
    )


@router.get("/objects/{object_id}", response_model=ApiEnvelope[BusinessObjectSummary])
async def get_business_object(
    object_id: UUID,
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[BusinessTruthStore, Depends(get_business_truth_store)],
    version: Annotated[int | None, Query(ge=1)] = None,
) -> ApiEnvelope[BusinessObjectSummary]:
    access.require("business_truth.read")
    try:
        record = await store.get_object(object_id, version)
    except (BusinessTruthNotFoundError, InvalidEvidenceCitationError) as error:
        raise_store_error(error)
    return ApiEnvelope(
        data=object_summary(record),
        meta=ApiMeta(request_id=request.state.request_id, source=store.source),
    )


@router.post(
    "/objects",
    response_model=ApiEnvelope[BusinessTruthMutationSummary],
    status_code=status.HTTP_201_CREATED,
)
async def create_business_object(
    payload: BusinessObjectCreate,
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[BusinessTruthStore, Depends(get_business_truth_store)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> ApiEnvelope[BusinessTruthMutationSummary]:
    access.require("business_truth.write")
    command = CreateBusinessObjectCommand(
        object_type=payload.object_type,
        slug=payload.slug,
        name=payload.name,
        status=payload.status,
        locale=payload.locale,
        payload=payload.payload,
        business_purpose=payload.business_purpose,
        change_summary=payload.change_summary,
        source_type=payload.source_type,
        source_ref=payload.source_ref,
        input_versions=payload.input_versions,
        citations=citation_drafts(payload.citations),
    )
    context = MutationContext(
        actor_type=access.actor.actor_type,
        actor_id=access.actor.subject_id,
        session_id=access.actor.session_id,
        request_id=request.state.request_id,
        idempotency_key=idempotency_key,
    )
    try:
        result = await store.create_object(command, context)
    except (
        BusinessTruthConflictError,
        BusinessTruthNotFoundError,
        InvalidEvidenceCitationError,
        InvalidBusinessTruthPayloadError,
    ) as error:
        raise_store_error(error)
    return ApiEnvelope(
        data=mutation_summary(result),
        meta=ApiMeta(request_id=request.state.request_id, source=store.source),
    )


@router.post(
    "/objects/{object_id}/versions",
    response_model=ApiEnvelope[BusinessTruthMutationSummary],
    status_code=status.HTTP_201_CREATED,
)
async def create_business_object_version(
    object_id: UUID,
    payload: BusinessObjectVersionCreate,
    request: Request,
    access: Annotated[AuthorizedWorkspace, Depends(require_workspace_access)],
    store: Annotated[BusinessTruthStore, Depends(get_business_truth_store)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> ApiEnvelope[BusinessTruthMutationSummary]:
    access.require("business_truth.write")
    command = CreateBusinessObjectVersionCommand(
        name=payload.name,
        status=payload.status,
        locale=payload.locale,
        payload=payload.payload,
        business_purpose=payload.business_purpose,
        change_summary=payload.change_summary,
        source_type=payload.source_type,
        source_ref=payload.source_ref,
        input_versions=payload.input_versions,
        citations=citation_drafts(payload.citations),
    )
    context = MutationContext(
        actor_type=access.actor.actor_type,
        actor_id=access.actor.subject_id,
        session_id=access.actor.session_id,
        request_id=request.state.request_id,
        idempotency_key=idempotency_key,
    )
    try:
        result = await store.create_version(object_id, command, context)
    except (
        BusinessTruthConflictError,
        BusinessTruthNotFoundError,
        InvalidEvidenceCitationError,
        InvalidBusinessTruthPayloadError,
    ) as error:
        raise_store_error(error)
    return ApiEnvelope(
        data=mutation_summary(result),
        meta=ApiMeta(request_id=request.state.request_id, source=store.source),
    )
