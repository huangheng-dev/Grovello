import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Literal, Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from grovello.models import (
    AuditEvent,
    BusinessObject,
    BusinessObjectVersion,
    BusinessTruthCitation,
    OutboxEvent,
)

type BusinessObjectType = Literal[
    "brand",
    "product",
    "offer",
    "price_book",
    "market",
    "icp",
    "evidence",
    "knowledge_document",
    "knowledge_chunk",
    "asset",
    "case_study",
]
type BusinessObjectStatus = Literal["draft", "active", "archived"]
type BusinessTruthSource = Literal["owner_edit", "import", "seed", "pipeline"]

PIPELINE_ONLY_OBJECT_TYPES: frozenset[BusinessObjectType] = frozenset({"knowledge_chunk"})

REQUIRED_PROFILE_OBJECT_TYPES: tuple[BusinessObjectType, ...] = (
    "brand",
    "product",
    "offer",
    "price_book",
    "market",
    "icp",
    "evidence",
    "knowledge_document",
    "asset",
    "case_study",
)


class BusinessTruthNotFoundError(LookupError):
    pass


class BusinessTruthConflictError(ValueError):
    pass


class InvalidEvidenceCitationError(ValueError):
    pass


class InvalidBusinessTruthPayloadError(ValueError):
    pass


def reject_pipeline_only_mutation(object_type: BusinessObjectType) -> None:
    if object_type in PIPELINE_ONLY_OBJECT_TYPES:
        raise InvalidBusinessTruthPayloadError(
            f"{object_type} can only be created by the governed knowledge pipeline"
        )


STRUCTURED_PAYLOAD_RULES: dict[BusinessObjectType, dict[str, object]] = {
    "evidence": {
        "required": (
            "evidenceType",
            "sourceTitle",
            "collectedAt",
            "sourceLocale",
            "verificationStatus",
            "reliability",
            "usageRights",
            "scope",
            "evidenceSummary",
            "keyFindings",
        ),
        "lists": ("keyFindings", "limitations"),
        "options": {
            "evidenceType": {
                "technical_record",
                "market_research",
                "customer_interview",
                "analytics_snapshot",
                "legal_document",
                "case_result",
                "third_party_report",
                "other",
            },
            "verificationStatus": {"verified", "owner_attested", "third_party", "unverified"},
            "reliability": {"high", "medium", "low"},
            "usageRights": {"owner_provided", "public_reference", "licensed", "internal_only"},
        },
    },
    "knowledge_document": {
        "required": (
            "documentType",
            "sourceLocale",
            "ownerTeam",
            "knowledgeStatus",
            "documentSummary",
            "knowledgeBody",
            "topics",
            "retrievalKeywords",
        ),
        "lists": ("topics", "retrievalKeywords", "audiences"),
        "options": {
            "documentType": {
                "product_guide",
                "faq",
                "policy",
                "playbook",
                "research_note",
                "technical_document",
                "training_material",
                "other",
            },
            "knowledgeStatus": {"working", "approved", "superseded"},
        },
    },
    "case_study": {
        "required": (
            "caseStudyType",
            "disclosureStatus",
            "customerDisplayName",
            "customerIndustry",
            "marketId",
            "productId",
            "engagementStartedAt",
            "caseSummary",
            "challenge",
            "approach",
            "outcomes",
            "lessons",
            "limitations",
            "approvedUseCases",
            "authorizationReference",
            "ownerTeam",
        ),
        "lists": ("lessons", "limitations", "approvedUseCases"),
        "references": ("marketId", "productId", "offerId", "icpId"),
        "rows": {
            "outcomes": ("metric", "result", "period", "evidenceNote"),
        },
        "options": {
            "caseStudyType": {
                "implementation",
                "customer_outcome",
                "pilot",
                "transformation",
                "partner_story",
                "internal_validation",
            },
            "disclosureStatus": {
                "public",
                "anonymized",
                "confidential",
                "fictional_fixture",
            },
        },
    },
}


def validate_business_truth_payload(
    object_type: BusinessObjectType,
    payload: dict,
    *,
    status: BusinessObjectStatus | None = None,
    citation_count: int = 0,
) -> None:
    rules = STRUCTURED_PAYLOAD_RULES.get(object_type)
    if rules is None:
        return
    required = rules["required"]
    missing = [field for field in required if not _has_payload_value(payload.get(field))]
    if missing:
        raise InvalidBusinessTruthPayloadError(
            f"{object_type} payload is missing required fields: {', '.join(missing)}"
        )
    for field in rules.get("lists", ()):
        value = payload.get(field)
        if value is not None and (
            not isinstance(value, list)
            or not all(isinstance(item, str) and item.strip() for item in value)
        ):
            raise InvalidBusinessTruthPayloadError(
                f"{object_type} payload field '{field}' must be a list of non-empty strings"
            )
    for field in rules.get("references", ()):
        value = payload.get(field)
        if value is None:
            continue
        try:
            UUID(str(value))
        except (TypeError, ValueError, AttributeError) as error:
            raise InvalidBusinessTruthPayloadError(
                f"{object_type} payload field '{field}' must contain a canonical UUID"
            ) from error
    for field, row_fields in rules.get("rows", {}).items():
        value = payload.get(field)
        if value is not None and (
            not isinstance(value, list)
            or not all(
                isinstance(row, dict)
                and all(
                    isinstance(row.get(row_field), str) and row[row_field].strip()
                    for row_field in row_fields
                )
                for row in value
            )
        ):
            raise InvalidBusinessTruthPayloadError(
                f"{object_type} payload field '{field}' must contain complete structured rows"
            )
    for field, allowed in rules.get("options", {}).items():
        value = payload.get(field)
        if value is not None and value not in allowed:
            raise InvalidBusinessTruthPayloadError(
                f"{object_type} payload field '{field}' contains an unsupported value"
            )
    if object_type == "case_study" and status == "active" and citation_count == 0:
        raise InvalidBusinessTruthPayloadError(
            "An active case_study must cite at least one exact evidence version"
        )


def _has_payload_value(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value)
    return value is not None


@dataclass(frozen=True, slots=True)
class CitationDraft:
    evidence_version_id: UUID
    claim_text: str
    locator: dict


@dataclass(frozen=True, slots=True)
class CreateBusinessObjectCommand:
    object_type: BusinessObjectType
    slug: str
    name: str
    status: BusinessObjectStatus
    locale: str
    payload: dict
    business_purpose: str
    change_summary: str
    source_type: BusinessTruthSource
    source_ref: str | None
    input_versions: dict
    citations: tuple[CitationDraft, ...]


@dataclass(frozen=True, slots=True)
class CreateBusinessObjectVersionCommand:
    name: str
    status: BusinessObjectStatus
    locale: str
    payload: dict
    business_purpose: str
    change_summary: str
    source_type: BusinessTruthSource
    source_ref: str | None
    input_versions: dict
    citations: tuple[CitationDraft, ...]


@dataclass(frozen=True, slots=True)
class MutationContext:
    actor_type: str
    actor_id: str
    session_id: str
    request_id: str
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class CitationRecord:
    id: UUID
    evidence_object_id: UUID
    evidence_version_id: UUID
    evidence_version: int
    evidence_name: str
    claim_text: str
    locator: dict


@dataclass(frozen=True, slots=True)
class BusinessObjectVersionRecord:
    id: UUID
    version: int
    schema_version: int
    name: str
    status: BusinessObjectStatus
    locale: str
    payload: dict
    business_purpose: str
    actor_id: str
    source_type: BusinessTruthSource
    source_ref: str | None
    change_summary: str
    input_versions: dict
    created_at: datetime
    citations: tuple[CitationRecord, ...]


@dataclass(frozen=True, slots=True)
class BusinessObjectRecord:
    id: UUID
    workspace_id: UUID
    object_type: BusinessObjectType
    slug: str
    current_version: int
    version: BusinessObjectVersionRecord


@dataclass(frozen=True, slots=True)
class BusinessTruthMutationResult:
    object: BusinessObjectRecord
    idempotent_replay: bool


@dataclass(frozen=True, slots=True)
class BusinessProfileRecord:
    workspace_id: UUID
    objects: tuple[BusinessObjectRecord, ...]
    missing_object_types: tuple[BusinessObjectType, ...]
    citation_count: int

    @property
    def is_complete(self) -> bool:
        return not self.missing_object_types and self.citation_count > 0


class BusinessTruthStore(Protocol):
    source: Literal["live", "seed"]

    async def create_object(
        self,
        command: CreateBusinessObjectCommand,
        context: MutationContext,
    ) -> BusinessTruthMutationResult: ...

    async def create_version(
        self,
        object_id: UUID,
        command: CreateBusinessObjectVersionCommand,
        context: MutationContext,
    ) -> BusinessTruthMutationResult: ...

    async def get_object(
        self,
        object_id: UUID,
        version: int | None = None,
    ) -> BusinessObjectRecord: ...

    async def get_profile(self) -> BusinessProfileRecord: ...


class SqlAlchemyBusinessTruthStore:
    source: Literal["live"] = "live"

    def __init__(self, session: AsyncSession, workspace_id: UUID) -> None:
        self._session = session
        self._workspace_id = workspace_id

    async def create_object(
        self,
        command: CreateBusinessObjectCommand,
        context: MutationContext,
    ) -> BusinessTruthMutationResult:
        reject_pipeline_only_mutation(command.object_type)
        replay = await self._version_for_idempotency_key(context.idempotency_key)
        if replay is not None:
            return BusinessTruthMutationResult(
                object=await self.get_object(replay.object_id, replay.version),
                idempotent_replay=True,
            )

        duplicate = await self._session.scalar(
            select(BusinessObject).where(
                BusinessObject.workspace_id == self._workspace_id,
                BusinessObject.object_type == command.object_type,
                BusinessObject.slug == command.slug,
            )
        )
        if duplicate is not None:
            raise BusinessTruthConflictError(
                f"A {command.object_type} with slug '{command.slug}' already exists"
            )

        validate_business_truth_payload(
            command.object_type,
            command.payload,
            status=command.status,
            citation_count=len(command.citations),
        )
        await self._validate_citations(command.citations)
        object_id = uuid.uuid4()
        version_id = uuid.uuid4()
        business_object = BusinessObject(
            id=object_id,
            workspace_id=self._workspace_id,
            object_type=command.object_type,
            slug=command.slug,
            name=command.name,
            status=command.status,
            current_version=1,
        )
        version = BusinessObjectVersion(
            id=version_id,
            workspace_id=self._workspace_id,
            object_id=object_id,
            version=1,
            schema_version=1,
            name=command.name,
            status=command.status,
            locale=command.locale,
            payload=command.payload,
            business_purpose=command.business_purpose,
            actor_id=context.actor_id,
            idempotency_key=context.idempotency_key,
            source_type=command.source_type,
            source_ref=command.source_ref,
            change_summary=command.change_summary,
            input_versions=command.input_versions,
        )
        self._session.add_all([business_object, version])
        self._add_citations(version_id, command.citations)
        self._add_lineage(business_object, version, command.business_purpose, context)
        await self._session.flush()
        return BusinessTruthMutationResult(
            object=await self.get_object(object_id, 1),
            idempotent_replay=False,
        )

    async def create_version(
        self,
        object_id: UUID,
        command: CreateBusinessObjectVersionCommand,
        context: MutationContext,
    ) -> BusinessTruthMutationResult:
        replay = await self._version_for_idempotency_key(context.idempotency_key)
        if replay is not None:
            if replay.object_id != object_id:
                raise BusinessTruthConflictError("Idempotency key belongs to another business object")
            replay_object = await self.get_object(object_id, replay.version)
            reject_pipeline_only_mutation(replay_object.object_type)
            return BusinessTruthMutationResult(
                object=replay_object,
                idempotent_replay=True,
            )

        business_object = await self._session.scalar(
            select(BusinessObject)
            .where(
                BusinessObject.workspace_id == self._workspace_id,
                BusinessObject.id == object_id,
            )
            .with_for_update()
        )
        if business_object is None or business_object.object_type in PIPELINE_ONLY_OBJECT_TYPES:
            raise BusinessTruthNotFoundError("Business object not found")
        reject_pipeline_only_mutation(business_object.object_type)

        validate_business_truth_payload(
            business_object.object_type,
            command.payload,
            status=command.status,
            citation_count=len(command.citations),
        )
        await self._validate_citations(command.citations)
        next_version = business_object.current_version + 1
        version = BusinessObjectVersion(
            id=uuid.uuid4(),
            workspace_id=self._workspace_id,
            object_id=object_id,
            version=next_version,
            schema_version=1,
            name=command.name,
            status=command.status,
            locale=command.locale,
            payload=command.payload,
            business_purpose=command.business_purpose,
            actor_id=context.actor_id,
            idempotency_key=context.idempotency_key,
            source_type=command.source_type,
            source_ref=command.source_ref,
            change_summary=command.change_summary,
            input_versions=command.input_versions,
        )
        business_object.name = command.name
        business_object.status = command.status
        business_object.current_version = next_version
        self._session.add(version)
        self._add_citations(version.id, command.citations)
        self._add_lineage(business_object, version, command.business_purpose, context)
        await self._session.flush()
        return BusinessTruthMutationResult(
            object=await self.get_object(object_id, next_version),
            idempotent_replay=False,
        )

    async def get_object(
        self,
        object_id: UUID,
        version: int | None = None,
    ) -> BusinessObjectRecord:
        business_object = await self._session.scalar(
            select(BusinessObject).where(
                BusinessObject.workspace_id == self._workspace_id,
                BusinessObject.id == object_id,
            )
        )
        if business_object is None or business_object.object_type in PIPELINE_ONLY_OBJECT_TYPES:
            raise BusinessTruthNotFoundError("Business object not found")
        selected_version = version or business_object.current_version
        version_row = await self._session.scalar(
            select(BusinessObjectVersion).where(
                BusinessObjectVersion.workspace_id == self._workspace_id,
                BusinessObjectVersion.object_id == object_id,
                BusinessObjectVersion.version == selected_version,
            )
        )
        if version_row is None:
            raise BusinessTruthNotFoundError("Business object version not found")
        return await self._to_record(business_object, version_row)

    async def get_profile(self) -> BusinessProfileRecord:
        objects = list(
            await self._session.scalars(
                select(BusinessObject)
                .where(
                    BusinessObject.workspace_id == self._workspace_id,
                    BusinessObject.object_type != "knowledge_chunk",
                )
                .order_by(BusinessObject.object_type, BusinessObject.slug)
            )
        )
        records = tuple([await self.get_object(item.id) for item in objects])
        return build_profile(self._workspace_id, records)

    async def _version_for_idempotency_key(
        self,
        idempotency_key: str,
    ) -> BusinessObjectVersion | None:
        return await self._session.scalar(
            select(BusinessObjectVersion).where(
                BusinessObjectVersion.workspace_id == self._workspace_id,
                BusinessObjectVersion.idempotency_key == idempotency_key,
            )
        )

    async def _validate_citations(self, citations: tuple[CitationDraft, ...]) -> None:
        for citation in citations:
            evidence_version = await self._session.scalar(
                select(BusinessObjectVersion).where(
                    BusinessObjectVersion.workspace_id == self._workspace_id,
                    BusinessObjectVersion.id == citation.evidence_version_id,
                )
            )
            if evidence_version is None:
                raise InvalidEvidenceCitationError("Evidence version not found")
            evidence_object = await self._session.scalar(
                select(BusinessObject).where(
                    BusinessObject.workspace_id == self._workspace_id,
                    BusinessObject.id == evidence_version.object_id,
                    BusinessObject.object_type == "evidence",
                )
            )
            if evidence_object is None:
                raise InvalidEvidenceCitationError("Citations must reference a versioned evidence object")

    def _add_citations(self, version_id: UUID, citations: tuple[CitationDraft, ...]) -> None:
        self._session.add_all(
            [
                BusinessTruthCitation(
                    id=uuid.uuid4(),
                    workspace_id=self._workspace_id,
                    citing_version_id=version_id,
                    evidence_version_id=citation.evidence_version_id,
                    claim_text=citation.claim_text,
                    locator=citation.locator,
                )
                for citation in citations
            ]
        )

    def _add_lineage(
        self,
        business_object: BusinessObject,
        version: BusinessObjectVersion,
        business_purpose: str,
        context: MutationContext,
    ) -> None:
        self._session.add_all(
            [
                AuditEvent(
                    id=uuid.uuid4(),
                    workspace_id=self._workspace_id,
                    actor_type=context.actor_type,
                    actor_id=context.actor_id,
                    session_id=context.session_id,
                    request_id=context.request_id,
                    action="business_truth.version_created",
                    resource_type=business_object.object_type,
                    resource_id=str(business_object.id),
                    outcome="succeeded",
                    reason=business_purpose,
                    evidence={
                        "version": version.version,
                        "sourceType": version.source_type,
                        "idempotencyKey": context.idempotency_key,
                    },
                ),
                OutboxEvent(
                    id=uuid.uuid4(),
                    workspace_id=self._workspace_id,
                    aggregate_type="BusinessObject",
                    aggregate_id=str(business_object.id),
                    event_type="BusinessTruthVersionCreated",
                    event_version=1,
                    payload={
                        "objectType": business_object.object_type,
                        "objectId": str(business_object.id),
                        "versionId": str(version.id),
                        "version": version.version,
                    },
                ),
            ]
        )

    async def _to_record(
        self,
        business_object: BusinessObject,
        version: BusinessObjectVersion,
    ) -> BusinessObjectRecord:
        citation_rows = list(
            await self._session.scalars(
                select(BusinessTruthCitation).where(
                    BusinessTruthCitation.workspace_id == self._workspace_id,
                    BusinessTruthCitation.citing_version_id == version.id,
                )
            )
        )
        citations: list[CitationRecord] = []
        for citation in citation_rows:
            evidence_version = await self._session.scalar(
                select(BusinessObjectVersion).where(
                    BusinessObjectVersion.workspace_id == self._workspace_id,
                    BusinessObjectVersion.id == citation.evidence_version_id,
                )
            )
            if evidence_version is None:
                raise InvalidEvidenceCitationError("Citation evidence version is unavailable")
            evidence_object = await self._session.scalar(
                select(BusinessObject).where(
                    BusinessObject.workspace_id == self._workspace_id,
                    BusinessObject.id == evidence_version.object_id,
                )
            )
            if evidence_object is None:
                raise InvalidEvidenceCitationError("Citation evidence object is unavailable")
            citations.append(
                CitationRecord(
                    id=citation.id,
                    evidence_object_id=evidence_object.id,
                    evidence_version_id=evidence_version.id,
                    evidence_version=evidence_version.version,
                    evidence_name=evidence_version.name,
                    claim_text=citation.claim_text,
                    locator=citation.locator,
                )
            )
        return BusinessObjectRecord(
            id=business_object.id,
            workspace_id=self._workspace_id,
            object_type=business_object.object_type,
            slug=business_object.slug,
            current_version=business_object.current_version,
            version=BusinessObjectVersionRecord(
                id=version.id,
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
                citations=tuple(citations),
            ),
        )


class InMemoryBusinessTruthStore:
    source: Literal["seed"] = "seed"

    def __init__(self, workspace_id: UUID) -> None:
        self._workspace_id = workspace_id
        self._objects: dict[UUID, BusinessObjectRecord] = {}
        self._versions: dict[tuple[UUID, int], BusinessObjectRecord] = {}
        self._idempotency: dict[str, tuple[UUID, int]] = {}

    async def create_object(
        self,
        command: CreateBusinessObjectCommand,
        context: MutationContext,
    ) -> BusinessTruthMutationResult:
        reject_pipeline_only_mutation(command.object_type)
        if replay := self._idempotency.get(context.idempotency_key):
            return BusinessTruthMutationResult(
                object=self._versions[replay],
                idempotent_replay=True,
            )
        if any(
            item.object_type == command.object_type and item.slug == command.slug
            for item in self._objects.values()
        ):
            raise BusinessTruthConflictError(
                f"A {command.object_type} with slug '{command.slug}' already exists"
            )
        validate_business_truth_payload(
            command.object_type,
            command.payload,
            status=command.status,
            citation_count=len(command.citations),
        )
        citations = self._resolve_citations(command.citations)
        object_id = uuid.uuid4()
        record = self._new_record(
            object_id=object_id,
            object_type=command.object_type,
            slug=command.slug,
            current_version=1,
            name=command.name,
            status=command.status,
            locale=command.locale,
            payload=command.payload,
            business_purpose=command.business_purpose,
            actor_id=context.actor_id,
            source_type=command.source_type,
            source_ref=command.source_ref,
            change_summary=command.change_summary,
            input_versions=command.input_versions,
            citations=citations,
        )
        self._objects[object_id] = record
        self._versions[(object_id, 1)] = record
        self._idempotency[context.idempotency_key] = (object_id, 1)
        return BusinessTruthMutationResult(object=record, idempotent_replay=False)

    async def create_version(
        self,
        object_id: UUID,
        command: CreateBusinessObjectVersionCommand,
        context: MutationContext,
    ) -> BusinessTruthMutationResult:
        if replay := self._idempotency.get(context.idempotency_key):
            if replay[0] != object_id:
                raise BusinessTruthConflictError("Idempotency key belongs to another business object")
            reject_pipeline_only_mutation(self._versions[replay].object_type)
            return BusinessTruthMutationResult(
                object=self._versions[replay],
                idempotent_replay=True,
            )
        current = self._objects.get(object_id)
        if current is None or current.object_type in PIPELINE_ONLY_OBJECT_TYPES:
            raise BusinessTruthNotFoundError("Business object not found")
        reject_pipeline_only_mutation(current.object_type)
        validate_business_truth_payload(
            current.object_type,
            command.payload,
            status=command.status,
            citation_count=len(command.citations),
        )
        citations = self._resolve_citations(command.citations)
        next_version = current.current_version + 1
        record = self._new_record(
            object_id=object_id,
            object_type=current.object_type,
            slug=current.slug,
            current_version=next_version,
            name=command.name,
            status=command.status,
            locale=command.locale,
            payload=command.payload,
            business_purpose=command.business_purpose,
            actor_id=context.actor_id,
            source_type=command.source_type,
            source_ref=command.source_ref,
            change_summary=command.change_summary,
            input_versions=command.input_versions,
            citations=citations,
        )
        self._objects[object_id] = record
        self._versions[(object_id, next_version)] = record
        self._idempotency[context.idempotency_key] = (object_id, next_version)
        return BusinessTruthMutationResult(object=record, idempotent_replay=False)

    async def get_object(
        self,
        object_id: UUID,
        version: int | None = None,
    ) -> BusinessObjectRecord:
        current = self._objects.get(object_id)
        if current is None or current.object_type in PIPELINE_ONLY_OBJECT_TYPES:
            raise BusinessTruthNotFoundError("Business object not found")
        if version is None:
            return current
        record = self._versions.get((object_id, version))
        if record is None:
            raise BusinessTruthNotFoundError("Business object version not found")
        return replace(record, current_version=current.current_version)

    async def get_profile(self) -> BusinessProfileRecord:
        records = tuple(
            sorted(
                (
                    item
                    for item in self._objects.values()
                    if item.object_type not in PIPELINE_ONLY_OBJECT_TYPES
                ),
                key=lambda item: (item.object_type, item.slug),
            )
        )
        return build_profile(self._workspace_id, records)

    def seed_object(
        self,
        *,
        object_type: BusinessObjectType,
        slug: str,
        name: str,
        payload: dict,
        citation_evidence_version_id: UUID | None = None,
    ) -> BusinessObjectRecord:
        reject_pipeline_only_mutation(object_type)
        object_id = uuid.uuid5(self._workspace_id, f"business-object:{object_type}:{slug}")
        citation_drafts = (
            (
                CitationDraft(
                    evidence_version_id=citation_evidence_version_id,
                    claim_text="Fictional acceptance claim supported by the referenced seed evidence.",
                    locator={"section": "acceptance-evidence"},
                ),
            )
            if citation_evidence_version_id
            else ()
        )
        citations = self._resolve_citations(citation_drafts)
        record = self._new_record(
            object_id=object_id,
            object_type=object_type,
            slug=slug,
            current_version=1,
            name=name,
            status="active",
            locale="en",
            payload=payload,
            business_purpose="Exercise the replaceable Global B2B Growth acceptance fixture",
            actor_id="grovello-seed",
            source_type="seed",
            source_ref="northstar-industrial-fixture",
            change_summary="Create fictional Phase 2 acceptance fixture",
            input_versions={},
            citations=citations,
        )
        self._objects[object_id] = record
        self._versions[(object_id, 1)] = record
        self._idempotency[f"seed-{object_type}-{slug}"] = (object_id, 1)
        return record

    def _resolve_citations(
        self,
        drafts: tuple[CitationDraft, ...],
    ) -> tuple[CitationRecord, ...]:
        citations: list[CitationRecord] = []
        for draft in drafts:
            evidence = next(
                (
                    item
                    for item in self._versions.values()
                    if item.version.id == draft.evidence_version_id and item.object_type == "evidence"
                ),
                None,
            )
            if evidence is None:
                raise InvalidEvidenceCitationError("Citations must reference a versioned evidence object")
            citations.append(
                CitationRecord(
                    id=uuid.uuid4(),
                    evidence_object_id=evidence.id,
                    evidence_version_id=evidence.version.id,
                    evidence_version=evidence.version.version,
                    evidence_name=evidence.version.name,
                    claim_text=draft.claim_text,
                    locator=draft.locator,
                )
            )
        return tuple(citations)

    def _new_record(
        self,
        *,
        object_id: UUID,
        object_type: BusinessObjectType,
        slug: str,
        current_version: int,
        name: str,
        status: BusinessObjectStatus,
        locale: str,
        payload: dict,
        business_purpose: str,
        actor_id: str,
        source_type: BusinessTruthSource,
        source_ref: str | None,
        change_summary: str,
        input_versions: dict,
        citations: tuple[CitationRecord, ...],
    ) -> BusinessObjectRecord:
        return BusinessObjectRecord(
            id=object_id,
            workspace_id=self._workspace_id,
            object_type=object_type,
            slug=slug,
            current_version=current_version,
            version=BusinessObjectVersionRecord(
                id=uuid.uuid4(),
                version=current_version,
                schema_version=1,
                name=name,
                status=status,
                locale=locale,
                payload=payload,
                business_purpose=business_purpose,
                actor_id=actor_id,
                source_type=source_type,
                source_ref=source_ref,
                change_summary=change_summary,
                input_versions=input_versions,
                created_at=datetime.now(UTC),
                citations=citations,
            ),
        )


def build_profile(
    workspace_id: UUID,
    records: tuple[BusinessObjectRecord, ...],
) -> BusinessProfileRecord:
    active_types = {item.object_type for item in records if item.version.status == "active"}
    missing = tuple(
        object_type for object_type in REQUIRED_PROFILE_OBJECT_TYPES if object_type not in active_types
    )
    return BusinessProfileRecord(
        workspace_id=workspace_id,
        objects=records,
        missing_object_types=missing,
        citation_count=sum(len(item.version.citations) for item in records),
    )


def northstar_business_truth_store(workspace_id: UUID) -> InMemoryBusinessTruthStore:
    store = InMemoryBusinessTruthStore(workspace_id)
    evidence = store.seed_object(
        object_type="evidence",
        slug="x200-acceptance-evidence",
        name="X200 fictional acceptance evidence",
        payload={"verificationState": "fictional_seed", "evidenceType": "technical_record"},
    )
    fixtures: tuple[tuple[BusinessObjectType, str, str, dict], ...] = (
        ("brand", "northstar-industrial", "Northstar Industrial", {"industry": "industrial automation"}),
        ("product", "servo-drive-x200", "Servo Drive X200", {"category": "servo drive"}),
        ("offer", "germany-launch-package", "Germany launch package", {"market": "DE"}),
        ("price_book", "eu-2026", "EU 2026 price book", {"currency": "EUR"}),
        ("market", "germany", "Germany", {"countryCode": "DE", "languages": ["de", "en"]}),
        ("icp", "german-machine-builders", "German machine builders", {"market": "DE"}),
        (
            "knowledge_document",
            "x200-overview",
            "X200 fictional product overview",
            {"verificationState": "fictional_seed"},
        ),
        ("asset", "x200-datasheet", "X200 fictional datasheet", {"mediaType": "application/pdf"}),
        (
            "case_study",
            "alpine-robotics-pilot",
            "Alpine Robotics fictional pilot",
            {"verificationState": "fictional_seed"},
        ),
    )
    for object_type, slug, name, payload in fixtures:
        store.seed_object(
            object_type=object_type,
            slug=slug,
            name=name,
            payload=payload,
            citation_evidence_version_id=(evidence.version.id if object_type == "product" else None),
        )
    return store
