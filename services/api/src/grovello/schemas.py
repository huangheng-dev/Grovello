from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from grovello.business_truth import BusinessObjectStatus, BusinessObjectType, BusinessTruthSource


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda value: "".join(
            [value.split("_")[0], *[part.title() for part in value.split("_")[1:]]]
        ),
        populate_by_name=True,
    )


class ApiMeta(ApiModel):
    request_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: Literal["live", "seed"] = "live"


class ApiEnvelope[EnvelopeData](ApiModel):
    data: EnvelopeData
    meta: ApiMeta


class HealthStatus(ApiModel):
    status: Literal["ok", "degraded"]
    service: str
    version: str
    environment: str


class ObjectStorageHealthStatus(ApiModel):
    status: Literal["ok", "degraded"]
    service: Literal["object-storage"] = "object-storage"
    provider: str
    configured: bool
    detail: str | None = None


class AssetScannerHealthStatus(ApiModel):
    status: Literal["ok", "degraded"]
    service: Literal["asset-scanner"] = "asset-scanner"
    provider: str
    configured: bool
    detail: str | None = None


class Capability(ApiModel):
    key: str
    name: str
    outcome: str
    state: Literal["foundation", "connected", "operational"]
    object_types: list[str]


class DashboardMetric(ApiModel):
    key: str
    label: str
    value: str
    delta: str


class DashboardOverview(ApiModel):
    metrics: list[DashboardMetric]
    pending_decisions: int
    active_runs: int
    data_notice: str


class WorkspaceSummary(ApiModel):
    id: str
    organization_id: str
    slug: str
    name: str
    default_locale: str
    timezone: str
    currency: str


class WorkspaceAccessSummary(ApiModel):
    workspace: WorkspaceSummary
    subject_id: str
    session_id: str
    roles: list[str]
    permissions: list[str]


type ImportableObjectType = Literal[
    "brand",
    "product",
    "offer",
    "price_book",
    "market",
    "icp",
    "evidence",
    "knowledge_document",
    "case_study",
]


class WorkspaceOnboardingCreate(ApiModel):
    business_purpose: str = Field(min_length=8, max_length=240)
    required_object_types: list[ImportableObjectType] = Field(min_length=1)
    input_versions: dict = Field(default_factory=dict)

    @field_validator("required_object_types")
    @classmethod
    def validate_required_object_types(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Required object types must be unique")
        return value


class WorkspaceOnboardingSummary(ApiModel):
    id: UUID
    workspace_id: UUID
    status: Literal["draft", "in_progress", "ready_for_review", "active", "blocked"]
    business_purpose: str
    required_object_types: list[str]
    validation_gaps: list[dict]
    input_versions: dict
    last_completed_step: str | None
    policy_version: int | None
    activation_version: int
    activated_by: str | None
    activated_at: datetime | None
    activation_business_purpose: str | None
    activation_snapshot: dict
    created_at: datetime
    updated_at: datetime


class WorkspaceOnboardingMutationSummary(ApiModel):
    onboarding: WorkspaceOnboardingSummary
    idempotent_replay: bool


class WorkspaceOnboardingActivation(ApiModel):
    business_purpose: str = Field(min_length=8, max_length=240)
    policy_version: int = Field(ge=1)
    reviewed_warning_codes: list[str] = Field(default_factory=list, max_length=100)


class ImportJobCreate(ApiModel):
    object_type: ImportableObjectType
    source_format: Literal["csv", "grovello_json"]
    schema_version: int = Field(default=1, ge=1)
    locale: Literal["en", "zh-CN"] = "en"
    original_filename: str = Field(min_length=1, max_length=500)
    content_type: Literal["text/csv", "application/json"]
    content_length: int = Field(gt=0)
    checksum_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    business_purpose: str = Field(min_length=8, max_length=240)
    input_versions: dict = Field(default_factory=dict)

    @field_validator("original_filename")
    @classmethod
    def validate_import_filename(cls, value: str) -> str:
        if value != value.strip() or "/" in value or "\\" in value or any(ord(char) < 32 for char in value):
            raise ValueError("Filename must be a plain file name without paths or control characters")
        return value


class ImportSourceSummary(ApiModel):
    id: UUID
    state: Literal[
        "uploading",
        "uploaded",
        "verifying",
        "scanning",
        "clean",
        "quarantined",
        "failed",
        "cancelled",
        "expired",
        "deleted",
    ]
    original_filename: str
    declared_mime_type: str
    declared_size: int
    declared_sha256: str
    verified_size: int | None
    verified_mime_type: str | None
    verified_sha256: str | None
    verified_at: datetime | None
    scan_status: Literal["not_started", "pending", "clean", "infected", "failed"]
    scan_provider: str | None
    scan_reference: str | None
    scan_attempts: int
    scanned_at: datetime | None
    quarantined_at: datetime | None
    expires_at: datetime
    deletion_deadline: datetime
    deleted_at: datetime | None


class ImportJobSummary(ApiModel):
    id: UUID
    workspace_id: UUID
    actor_id: str
    business_purpose: str
    object_type: ImportableObjectType
    source_format: Literal["csv", "grovello_json"]
    schema_version: int
    locale: str
    status: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    applied_rows: int
    workflow_id: str | None
    selected_mapping_version_id: UUID | None
    validation_workflow_id: str | None
    parser_version: str | None
    selected_change_set_id: UUID | None
    apply_workflow_id: str | None
    compensation_workflow_id: str | None
    compensation_policy_version: int | None
    compensation_business_purpose: str | None
    input_versions: dict
    result_summary: dict
    failure_code: str | None
    failure_detail: str | None
    retention_deadline: datetime
    cancelled_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    source: ImportSourceSummary


class ImportUploadGrantSummary(ApiModel):
    method: Literal["POST"]
    url: str
    fields: dict[str, str]
    expires_at: datetime


class ImportJobCreateSummary(ApiModel):
    job: ImportJobSummary
    upload: ImportUploadGrantSummary
    idempotent_replay: bool


class ImportJobMutationSummary(ApiModel):
    job: ImportJobSummary
    idempotent_replay: bool


class ImportMappingFieldInput(ApiModel):
    source: str | None = Field(default=None, min_length=1, max_length=240)
    target: str = Field(min_length=1, max_length=240)
    transform: Literal[
        "identity", "trim", "lowercase", "uppercase", "integer", "decimal", "boolean", "json", "split"
    ] = "identity"
    default_value: Any = None
    has_default: bool = False
    separator: str = Field(default=",", min_length=1, max_length=4)


class ImportMappingCreate(ApiModel):
    source_fields: list[str] = Field(min_length=1, max_length=100)
    delimiter: Literal[",", ";", "\t", "|"] | None = None
    fields: list[ImportMappingFieldInput] = Field(min_length=1, max_length=100)
    business_purpose: str = Field(min_length=8, max_length=240)

    @field_validator("source_fields")
    @classmethod
    def validate_source_fields(cls, value: list[str]) -> list[str]:
        if any(
            not field.strip()
            or field != field.strip()
            or len(field) > 240
            or any(ord(character) < 32 for character in field)
            for field in value
        ):
            raise ValueError("Source fields must be trimmed and non-empty")
        if len(value) != len(set(value)):
            raise ValueError("Source fields must be unique")
        return value


class ImportMappingFieldSummary(ApiModel):
    source: str | None
    target: str
    transform: str
    default_value: Any
    has_default: bool
    separator: str


class ImportMappingSummary(ApiModel):
    id: UUID
    job_id: UUID
    version: int
    schema_fingerprint: str
    business_purpose: str | None
    source_fields: list[str]
    delimiter: str | None
    fields: list[ImportMappingFieldSummary]
    created_by: str
    created_at: datetime


class ImportMappingMutationSummary(ApiModel):
    mapping: ImportMappingSummary
    idempotent_replay: bool


class ImportValidationStart(ApiModel):
    business_purpose: str = Field(min_length=8, max_length=240)


class ImportValidationMutationSummary(ApiModel):
    job: ImportJobSummary
    idempotent_replay: bool


class ImportPreviewRowSummary(ApiModel):
    source_row_number: int
    status: str
    normalized_data: dict
    target_identity: dict


class ImportIssueSummary(ApiModel):
    source_row_number: int | None
    code: str
    severity: str
    field_locator: dict
    message: str
    redacted_sample: str | None


class ImportValidationReportSummary(ApiModel):
    job: ImportJobSummary
    mapping: ImportMappingSummary | None
    preview: list[ImportPreviewRowSummary]
    issues: list[ImportIssueSummary]


class ImportChangeSetCreate(ApiModel):
    business_purpose: str = Field(min_length=8, max_length=240)
    policy_version: int | None = Field(default=None, ge=1)


class ImportChangeSetApproval(ApiModel):
    decision: Literal["approved", "rejected"]
    reason: str = Field(min_length=8, max_length=500)
    policy_version: int = Field(ge=1)


class ImportCompensationRequest(ApiModel):
    business_purpose: str = Field(min_length=8, max_length=240)
    policy_version: int = Field(ge=1)


class ImportChangeSetOperationSummary(ApiModel):
    id: UUID
    source_row_number: int
    operation: Literal["create", "new_version", "skip", "conflict"]
    status: Literal["planned", "applied", "skipped", "failed", "compensated"]
    target_object_id: UUID | None
    expected_version_id: UUID | None
    expected_version: int | None
    result_object_id: UUID | None
    result_version_id: UUID | None
    result_version: int | None
    failure_code: str | None


class ImportChangeSetSummary(ApiModel):
    id: UUID
    job_id: UUID
    version: int
    plan_hash: str
    status: Literal["draft", "ready_for_review", "approved", "rejected", "applied", "superseded"]
    approval_state: Literal["not_required", "pending", "approved", "rejected"]
    approval_policy_version: int | None
    approval_requested_by: str | None
    approval_requested_at: datetime | None
    approval_decided_by: str | None
    approval_decided_at: datetime | None
    approval_reason: str | None
    business_purpose: str
    summary: dict
    operations: list[ImportChangeSetOperationSummary]
    created_by: str
    created_at: datetime


class ImportChangeSetMutationSummary(ApiModel):
    change_set: ImportChangeSetSummary
    idempotent_replay: bool


class ImportWorkflowMutationSummary(ApiModel):
    change_set: ImportChangeSetSummary
    workflow_id: str
    idempotent_replay: bool


class AuditEventSummary(ApiModel):
    id: str
    workspace_id: str
    actor_type: str
    actor_id: str
    session_id: str
    action: str
    resource_type: str
    resource_id: str
    outcome: str
    request_id: str
    evidence: dict


class RecoveryPlan(ApiModel):
    workspace_id: str
    status: Literal["ready", "blocked"]
    required_permission: str
    safeguards: list[str]


class BusinessTruthCitationInput(ApiModel):
    evidence_version_id: UUID
    claim_text: str = Field(min_length=1, max_length=2000)
    locator: dict = Field(default_factory=dict)


class BusinessObjectCreate(ApiModel):
    object_type: BusinessObjectType
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", min_length=2, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    status: BusinessObjectStatus = "draft"
    locale: str = Field(default="en", min_length=2, max_length=12)
    payload: dict
    business_purpose: str = Field(min_length=8, max_length=240)
    change_summary: str = Field(min_length=3, max_length=500)
    source_type: BusinessTruthSource = "owner_edit"
    source_ref: str | None = Field(default=None, max_length=500)
    input_versions: dict = Field(default_factory=dict)
    citations: list[BusinessTruthCitationInput] = Field(default_factory=list)


class BusinessObjectVersionCreate(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    status: BusinessObjectStatus = "draft"
    locale: str = Field(default="en", min_length=2, max_length=12)
    payload: dict
    business_purpose: str = Field(min_length=8, max_length=240)
    change_summary: str = Field(min_length=3, max_length=500)
    source_type: BusinessTruthSource = "owner_edit"
    source_ref: str | None = Field(default=None, max_length=500)
    input_versions: dict = Field(default_factory=dict)
    citations: list[BusinessTruthCitationInput] = Field(default_factory=list)


class BusinessTruthCitationSummary(ApiModel):
    id: str
    evidence_object_id: str
    evidence_version_id: str
    evidence_version: int
    evidence_name: str
    claim_text: str
    locator: dict


class BusinessObjectVersionSummary(ApiModel):
    id: str
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
    citations: list[BusinessTruthCitationSummary]


class BusinessObjectSummary(ApiModel):
    id: str
    workspace_id: str
    object_type: BusinessObjectType
    slug: str
    current_version: int
    version: BusinessObjectVersionSummary


class BusinessTruthMutationSummary(ApiModel):
    object: BusinessObjectSummary
    idempotent_replay: bool


class BusinessProfileSummary(ApiModel):
    workspace_id: str
    validation_state: Literal["complete", "incomplete"]
    object_count: int
    citation_count: int
    missing_object_types: list[BusinessObjectType]
    objects: list[BusinessObjectSummary]


class AssetUploadSessionCreate(ApiModel):
    original_filename: str = Field(min_length=1, max_length=500)
    content_type: str = Field(min_length=1, max_length=255)
    content_length: int = Field(gt=0)
    checksum_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    business_purpose: str = Field(min_length=8, max_length=240)
    target_asset_id: UUID | None = None

    @field_validator("original_filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        if value != value.strip() or "/" in value or "\\" in value or any(ord(char) < 32 for char in value):
            raise ValueError("Filename must be a plain file name without paths or control characters")
        return value


class AssetUploadGrantSummary(ApiModel):
    method: Literal["POST"]
    url: str
    fields: dict[str, str]
    expires_at: datetime


class AssetUploadSessionSummary(ApiModel):
    id: UUID
    workspace_id: UUID
    target_asset_id: UUID | None
    actor_id: str
    business_purpose: str
    state: str
    scan_status: Literal["not_started", "pending", "clean", "infected", "failed"]
    scan_provider: str | None
    scan_reference: str | None
    scan_attempts: int
    scanned_at: datetime | None
    quarantine_object_key: str | None
    quarantined_at: datetime | None
    finalization_workflow_id: str | None
    finalized_blob_id: UUID | None
    finalized_asset_id: UUID | None
    finalized_asset_version_id: UUID | None
    finalized_at: datetime | None
    staging_cleanup_status: Literal["not_started", "pending", "complete", "failed"]
    staging_cleanup_at: datetime | None
    original_filename: str
    declared_mime_type: str
    declared_size: int
    declared_sha256: str
    expires_at: datetime
    completed_at: datetime | None
    cancelled_at: datetime | None
    workflow_id: str | None
    failure_code: str | None
    failure_detail: str | None
    verified_size: int | None
    verified_sha256: str | None
    verified_mime_type: str | None
    verified_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AssetUploadCreateSummary(ApiModel):
    session: AssetUploadSessionSummary
    upload: AssetUploadGrantSummary
    idempotent_replay: bool


class AssetUploadMutationSummary(ApiModel):
    session: AssetUploadSessionSummary
    idempotent_replay: bool


class AssetFinalizationRequest(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    locale: Literal["en", "zh-CN"] = "en"
    status: Literal["draft", "active"] = "draft"
    metadata: dict = Field(default_factory=dict)
    change_summary: str = Field(min_length=8, max_length=500)


class AssetDownloadSummary(ApiModel):
    asset_id: UUID
    asset_version_id: UUID
    blob_id: UUID
    filename: str
    content_type: str
    byte_size: int
    sha256: str
    url: str
    expires_at: datetime
    headers: dict[str, str]


class AssetFileSummary(ApiModel):
    blob_id: UUID
    filename: str
    content_type: str
    byte_size: int
    sha256: str
    scan_status: Literal["pending", "clean", "infected", "failed"]
    storage_status: Literal["available", "quarantined", "purge_pending", "purged"]


class AssetCatalogVersionSummary(ApiModel):
    id: UUID
    version: int
    name: str
    status: Literal["draft", "active", "archived"]
    locale: str
    payload: dict
    change_summary: str
    created_at: datetime
    original_file: AssetFileSummary | None
    downloadable: bool


class AssetCatalogItemSummary(ApiModel):
    id: UUID
    slug: str
    name: str
    status: Literal["draft", "active", "archived"]
    current_version: int
    updated_at: datetime
    versions: list[AssetCatalogVersionSummary]


class AssetCatalogSummary(ApiModel):
    items: list[AssetCatalogItemSummary]
