import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"
    __table_args__ = (UniqueConstraint("slug"), Index("ix_organizations_slug", "slug"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(32), default="active")
    workspaces: Mapped[list["Workspace"]] = relationship(back_populates="organization")


class Workspace(TimestampMixin, Base):
    __tablename__ = "workspaces"
    __table_args__ = (UniqueConstraint("slug"), Index("ix_workspaces_slug", "slug"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    slug: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(160))
    default_locale: Mapped[str] = mapped_column(String(12), default="en")
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    organization: Mapped[Organization] = relationship(back_populates="workspaces")
    goals: Mapped[list["Goal"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("external_subject"),
        Index("ix_users_external_subject", "external_subject"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    external_subject: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(320), index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(32), default="active")


class Team(TimestampMixin, Base):
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("workspace_id", "slug"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    slug: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(160))


class WorkspaceMembership(TimestampMixin, Base):
    __tablename__ = "workspace_memberships"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="active")


class Role(TimestampMixin, Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("workspace_id", "key"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)


class Permission(Base):
    __tablename__ = "permissions"
    key: Mapped[str] = mapped_column(String(160), primary_key=True)
    description: Mapped[str] = mapped_column(String(255))
    risk_tier: Mapped[str] = mapped_column(String(2), default="R0")


class RolePermission(Base):
    __tablename__ = "role_permissions"
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_key: Mapped[str] = mapped_column(
        ForeignKey("permissions.key", ondelete="CASCADE"), primary_key=True
    )


class MembershipRole(Base):
    __tablename__ = "membership_roles"
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    membership_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspace_memberships.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)


class Policy(TimestampMixin, Base):
    __tablename__ = "policies"
    __table_args__ = (UniqueConstraint("workspace_id", "key", "version"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    rules: Mapped[dict] = mapped_column(JSON, default=dict)


class UserSession(TimestampMixin, Base):
    __tablename__ = "user_sessions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    identity_provider: Mapped[str] = mapped_column(String(80))
    provider_session_id_hash: Mapped[str] = mapped_column(String(128), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class Goal(TimestampMixin, Base):
    __tablename__ = "goals"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    metric_key: Mapped[str] = mapped_column(String(100))
    target_value: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    currency: Mapped[str | None] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(32), default="draft")
    constraints: Mapped[dict] = mapped_column(JSON, default=dict)
    workspace: Mapped[Workspace] = relationship(back_populates="goals")


class Run(TimestampMixin, Base):
    __tablename__ = "runs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    workflow_type: Mapped[str] = mapped_column(String(120), index=True)
    workflow_id: Mapped[str] = mapped_column(String(180), unique=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    input_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    result_summary: Mapped[dict] = mapped_column(JSON, default=dict)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    actor_type: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[str] = mapped_column(String(180))
    session_id: Mapped[str | None] = mapped_column(String(180), index=True)
    request_id: Mapped[str | None] = mapped_column(String(180), index=True)
    action: Mapped[str] = mapped_column(String(160), index=True)
    resource_type: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[str] = mapped_column(String(180))
    outcome: Mapped[str] = mapped_column(String(32), default="succeeded")
    reason: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    aggregate_type: Mapped[str] = mapped_column(String(100), index=True)
    aggregate_id: Mapped[str] = mapped_column(String(180), index=True)
    event_type: Mapped[str] = mapped_column(String(160), index=True)
    event_version: Mapped[int] = mapped_column(default=1)
    payload: Mapped[dict] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class BusinessObject(TimestampMixin, Base):
    __tablename__ = "business_objects"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "object_type", "slug"),
        CheckConstraint(
            "object_type IN ('brand', 'product', 'offer', 'price_book', 'market', 'icp', "
            "'evidence', 'knowledge_document', 'knowledge_chunk', 'asset', 'case_study')",
            name="ck_business_objects_object_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'active', 'archived')",
            name="ck_business_objects_status",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    object_type: Mapped[str] = mapped_column(String(40), index=True)
    slug: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(32), default="draft")
    current_version: Mapped[int] = mapped_column(Integer, default=1)


class BusinessObjectVersion(Base):
    __tablename__ = "business_object_versions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint(
            "workspace_id",
            "object_id",
            "id",
            name="uq_business_object_versions_workspace_object_id_id",
        ),
        UniqueConstraint("workspace_id", "object_id", "version"),
        UniqueConstraint("workspace_id", "idempotency_key"),
        ForeignKeyConstraint(
            ["workspace_id", "object_id"],
            ["business_objects.workspace_id", "business_objects.id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("version > 0", name="ck_business_object_versions_version"),
        CheckConstraint("schema_version > 0", name="ck_business_object_versions_schema_version"),
        CheckConstraint(
            "status IN ('draft', 'active', 'archived')",
            name="ck_business_object_versions_status",
        ),
        CheckConstraint(
            "source_type IN ('owner_edit', 'import', 'seed', 'pipeline')",
            name="ck_business_object_versions_source_type",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    version: Mapped[int] = mapped_column(Integer)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(32), default="draft")
    locale: Mapped[str] = mapped_column(String(12), default="en")
    payload: Mapped[dict] = mapped_column(JSON)
    business_purpose: Mapped[str] = mapped_column(String(240))
    actor_id: Mapped[str] = mapped_column(String(180), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    source_type: Mapped[str] = mapped_column(String(32), default="owner_edit")
    source_ref: Mapped[str | None] = mapped_column(String(500))
    change_summary: Mapped[str] = mapped_column(String(500))
    input_versions: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BusinessTruthCitation(Base):
    __tablename__ = "business_truth_citations"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        ForeignKeyConstraint(
            ["workspace_id", "citing_version_id"],
            ["business_object_versions.workspace_id", "business_object_versions.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "evidence_version_id"],
            ["business_object_versions.workspace_id", "business_object_versions.id"],
            ondelete="CASCADE",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    citing_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    evidence_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    claim_text: Mapped[str] = mapped_column(Text)
    locator: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeIngestion(TimestampMixin, Base):
    __tablename__ = "knowledge_ingestions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "idempotency_key"),
        UniqueConstraint("workflow_id"),
        ForeignKeyConstraint(
            ["workspace_id", "source_object_id"],
            ["business_objects.workspace_id", "business_objects.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "source_object_id", "source_version_id"],
            [
                "business_object_versions.workspace_id",
                "business_object_versions.object_id",
                "business_object_versions.id",
            ],
        ),
        CheckConstraint(
            "source_object_type IN ('knowledge_document', 'evidence', 'case_study', 'asset')",
            name="ck_knowledge_ingestions_source_object_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'ready', 'failed', 'cancelled')",
            name="ck_knowledge_ingestions_status",
        ),
        CheckConstraint(
            "request_hash ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_ingestions_request_hash",
        ),
        CheckConstraint(
            "approval_policy_version IS NULL OR approval_policy_version > 0",
            name="ck_knowledge_ingestions_policy_version",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    source_object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    source_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    source_object_type: Mapped[str] = mapped_column(String(40))
    actor_id: Mapped[str] = mapped_column(String(180), index=True)
    session_id: Mapped[str | None] = mapped_column(String(180))
    request_id: Mapped[str | None] = mapped_column(String(180))
    idempotency_key: Mapped[str] = mapped_column(String(180))
    request_hash: Mapped[str] = mapped_column(String(64))
    business_purpose: Mapped[str] = mapped_column(String(240))
    pipeline_profile: Mapped[str] = mapped_column(String(120))
    pipeline_version: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    input_versions: Mapped[dict] = mapped_column(JSON, default=dict)
    approval_policy_version: Mapped[int | None] = mapped_column(Integer)
    workflow_id: Mapped[str | None] = mapped_column(String(180), index=True)
    workflow_run_id: Mapped[str | None] = mapped_column(String(180))
    cost_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    failure_code: Mapped[str | None] = mapped_column(String(100))
    failure_detail: Mapped[str | None] = mapped_column(Text)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class KnowledgeSourceSnapshot(Base):
    __tablename__ = "knowledge_source_snapshots"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "ingestion_id"),
        ForeignKeyConstraint(
            ["workspace_id", "ingestion_id"],
            ["knowledge_ingestions.workspace_id", "knowledge_ingestions.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "source_object_id"],
            ["business_objects.workspace_id", "business_objects.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "source_object_id", "source_version_id"],
            [
                "business_object_versions.workspace_id",
                "business_object_versions.object_id",
                "business_object_versions.id",
            ],
        ),
        CheckConstraint(
            "source_object_type IN ('knowledge_document', 'evidence', 'case_study', 'asset')",
            name="ck_knowledge_source_snapshots_source_object_type",
        ),
        CheckConstraint(
            "content_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_source_snapshots_content_sha256",
        ),
        CheckConstraint(
            "policy_version IS NULL OR policy_version > 0",
            name="ck_knowledge_source_snapshots_policy_version",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    ingestion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    source_object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    source_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    source_object_type: Mapped[str] = mapped_column(String(40))
    content_sha256: Mapped[str] = mapped_column(String(64))
    locale: Mapped[str] = mapped_column(String(12))
    source_status: Mapped[str] = mapped_column(String(32))
    usage_rights: Mapped[str] = mapped_column(String(64))
    sensitivity: Mapped[str] = mapped_column(String(32))
    parser_eligible: Mapped[bool] = mapped_column(Boolean)
    source_locator: Mapped[dict] = mapped_column(JSON, default=dict)
    source_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    policy_version: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeGeneration(TimestampMixin, Base):
    __tablename__ = "knowledge_generations"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "ingestion_id"),
        ForeignKeyConstraint(
            ["workspace_id", "ingestion_id"],
            ["knowledge_ingestions.workspace_id", "knowledge_ingestions.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "source_snapshot_id"],
            ["knowledge_source_snapshots.workspace_id", "knowledge_source_snapshots.id"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('pending', 'building', 'staged', 'active', 'retired', 'failed')",
            name="ck_knowledge_generations_status",
        ),
        CheckConstraint("chunk_count >= 0", name="ck_knowledge_generations_chunk_count"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    ingestion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    source_snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    pipeline_profile: Mapped[str] = mapped_column(String(120))
    pipeline_version: Mapped[str] = mapped_column(String(80))
    parser_profile: Mapped[str] = mapped_column(String(120), default="canonical-json-v1")
    normalizer_version: Mapped[str] = mapped_column(String(80), default="none")
    classifier_version: Mapped[str] = mapped_column(String(80), default="none")
    chunker_version: Mapped[str] = mapped_column(String(80), default="none")
    embedding_config: Mapped[dict] = mapped_column(JSON, default=dict)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class KnowledgeGenerationChunk(Base):
    __tablename__ = "knowledge_generation_chunks"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "generation_id", "ordinal"),
        UniqueConstraint("workspace_id", "chunk_version_id"),
        ForeignKeyConstraint(
            ["workspace_id", "generation_id"],
            ["knowledge_generations.workspace_id", "knowledge_generations.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "chunk_object_id"],
            ["business_objects.workspace_id", "business_objects.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "chunk_object_id", "chunk_version_id"],
            [
                "business_object_versions.workspace_id",
                "business_object_versions.object_id",
                "business_object_versions.id",
            ],
            ondelete="CASCADE",
        ),
        CheckConstraint("ordinal > 0", name="ck_knowledge_generation_chunks_ordinal"),
        CheckConstraint(
            "content_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_generation_chunks_content_sha256",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    generation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    chunk_object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    chunk_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    content_sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeRetrievalReceipt(Base):
    __tablename__ = "knowledge_retrieval_receipts"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        CheckConstraint(
            "query_hash ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_retrieval_receipts_query_hash",
        ),
        CheckConstraint(
            "semantic_status IN ('unavailable', 'available', 'degraded')",
            name="ck_knowledge_retrieval_receipts_semantic_status",
        ),
        CheckConstraint(
            "policy_version IS NULL OR policy_version > 0",
            name="ck_knowledge_retrieval_receipts_policy_version",
        ),
        CheckConstraint("result_count >= 0", name="ck_knowledge_retrieval_receipts_result_count"),
        CheckConstraint("latency_ms >= 0", name="ck_knowledge_retrieval_receipts_latency_ms"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    actor_id: Mapped[str] = mapped_column(String(180), index=True)
    session_id: Mapped[str | None] = mapped_column(String(180))
    request_id: Mapped[str | None] = mapped_column(String(180))
    business_purpose: Mapped[str] = mapped_column(String(240))
    query_hash: Mapped[str] = mapped_column(String(64), index=True)
    query_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    policy_version: Mapped[int | None] = mapped_column(Integer)
    lexical_config: Mapped[dict] = mapped_column(JSON, default=dict)
    vector_config: Mapped[dict] = mapped_column(JSON, default=dict)
    semantic_status: Mapped[str] = mapped_column(String(32), default="unavailable")
    result_chunk_version_ids: Mapped[list] = mapped_column(JSON, default=list)
    score_components: Mapped[list] = mapped_column(JSON, default=list)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class AssetUploadSession(TimestampMixin, Base):
    __tablename__ = "asset_upload_sessions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "idempotency_key"),
        UniqueConstraint("workspace_id", "staging_object_key"),
        UniqueConstraint("workspace_id", "completion_idempotency_key"),
        UniqueConstraint("workspace_id", "finalization_idempotency_key"),
        ForeignKeyConstraint(
            ["workspace_id", "target_asset_id"],
            ["business_objects.workspace_id", "business_objects.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "finalized_blob_id"],
            ["asset_blobs.workspace_id", "asset_blobs.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "finalized_asset_id"],
            ["business_objects.workspace_id", "business_objects.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "finalized_asset_version_id"],
            ["business_object_versions.workspace_id", "business_object_versions.id"],
        ),
        CheckConstraint(
            "state IN ('initiated', 'uploaded', 'verifying', 'scanning', "
            "'ready_to_finalize', 'finalizing', 'finalized', 'failed', 'expired', 'cancelled', "
            "'quarantined')",
            name="ck_asset_upload_sessions_state",
        ),
        CheckConstraint("declared_size > 0", name="ck_asset_upload_sessions_declared_size"),
        CheckConstraint(
            "declared_sha256 IS NULL OR declared_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_asset_upload_sessions_declared_sha256",
        ),
        CheckConstraint(
            "scan_status IN ('not_started', 'pending', 'clean', 'infected', 'failed')",
            name="ck_asset_upload_sessions_scan_status",
        ),
        CheckConstraint("scan_attempts >= 0", name="ck_asset_upload_sessions_scan_attempts"),
        CheckConstraint(
            "finalization_request_hash IS NULL OR finalization_request_hash ~ '^[0-9a-f]{64}$'",
            name="ck_asset_upload_sessions_finalization_request_hash",
        ),
        CheckConstraint(
            "staging_cleanup_status IN ('not_started', 'pending', 'complete', 'failed')",
            name="ck_asset_upload_sessions_staging_cleanup_status",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    target_asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    actor_id: Mapped[str] = mapped_column(String(180), index=True)
    business_purpose: Mapped[str] = mapped_column(String(240))
    session_id: Mapped[str | None] = mapped_column(String(180), index=True)
    request_id: Mapped[str | None] = mapped_column(String(180), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    completion_idempotency_key: Mapped[str | None] = mapped_column(String(180))
    workflow_id: Mapped[str | None] = mapped_column(String(180), unique=True, index=True)
    state: Mapped[str] = mapped_column(String(32), default="initiated", index=True)
    original_filename: Mapped[str] = mapped_column(String(500))
    declared_mime_type: Mapped[str] = mapped_column(String(255))
    declared_size: Mapped[int] = mapped_column(BigInteger)
    declared_sha256: Mapped[str | None] = mapped_column(String(64))
    staging_object_key: Mapped[str] = mapped_column(String(1024))
    multipart_upload_id: Mapped[str | None] = mapped_column(String(1024))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(100))
    failure_detail: Mapped[str | None] = mapped_column(Text)
    verified_size: Mapped[int | None] = mapped_column(BigInteger)
    verified_sha256: Mapped[str | None] = mapped_column(String(64))
    verified_mime_type: Mapped[str | None] = mapped_column(String(255))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_provider_version_id: Mapped[str | None] = mapped_column(String(1024))
    verified_etag: Mapped[str | None] = mapped_column(String(255))
    scan_status: Mapped[str] = mapped_column(String(32), default="not_started", index=True)
    scan_provider: Mapped[str | None] = mapped_column(String(120))
    scan_reference: Mapped[str | None] = mapped_column(String(500))
    scan_attempts: Mapped[int] = mapped_column(Integer, default=0)
    scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quarantine_object_key: Mapped[str | None] = mapped_column(String(1024))
    quarantine_provider_version_id: Mapped[str | None] = mapped_column(String(1024))
    quarantined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finalization_idempotency_key: Mapped[str | None] = mapped_column(String(180))
    finalization_request_hash: Mapped[str | None] = mapped_column(String(64))
    finalization_payload: Mapped[dict | None] = mapped_column(JSONB)
    finalization_workflow_id: Mapped[str | None] = mapped_column(String(180), unique=True, index=True)
    finalized_blob_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    finalized_asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    finalized_asset_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    staging_cleanup_status: Mapped[str] = mapped_column(String(32), default="not_started", index=True)
    staging_cleanup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AssetBlob(Base):
    __tablename__ = "asset_blobs"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "storage_profile", "object_key"),
        CheckConstraint("byte_size > 0", name="ck_asset_blobs_byte_size"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_asset_blobs_sha256"),
        CheckConstraint(
            "scan_status IN ('pending', 'clean', 'infected', 'failed')",
            name="ck_asset_blobs_scan_status",
        ),
        CheckConstraint(
            "storage_status IN ('available', 'quarantined', 'purge_pending', 'purged')",
            name="ck_asset_blobs_storage_status",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    storage_profile: Mapped[str] = mapped_column(String(80), default="default")
    object_key: Mapped[str] = mapped_column(String(1024))
    provider_version_id: Mapped[str | None] = mapped_column(String(1024))
    etag: Mapped[str | None] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    byte_size: Mapped[int] = mapped_column(BigInteger)
    detected_mime_type: Mapped[str] = mapped_column(String(255))
    scan_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    scan_provider: Mapped[str | None] = mapped_column(String(120))
    scan_reference: Mapped[str | None] = mapped_column(String(500))
    storage_status: Mapped[str] = mapped_column(String(32), default="available", index=True)
    encryption_mode: Mapped[str] = mapped_column(String(32), default="sse-s3")
    encryption_key_ref: Mapped[str | None] = mapped_column(String(500))
    retained_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AssetVersionFile(Base):
    __tablename__ = "asset_version_files"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "business_object_version_id", "role", "variant_key"),
        ForeignKeyConstraint(
            ["workspace_id", "business_object_version_id"],
            ["business_object_versions.workspace_id", "business_object_versions.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "blob_id"],
            ["asset_blobs.workspace_id", "asset_blobs.id"],
        ),
        CheckConstraint(
            "role IN ('original', 'thumbnail', 'preview', 'transcript', 'caption')",
            name="ck_asset_version_files_role",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    business_object_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    blob_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    role: Mapped[str] = mapped_column(String(32), default="original")
    variant_key: Mapped[str] = mapped_column(String(80), default="default")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkspaceOnboarding(TimestampMixin, Base):
    __tablename__ = "workspace_onboardings"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id"),
        UniqueConstraint("workspace_id", "idempotency_key"),
        UniqueConstraint(
            "workspace_id",
            "activation_idempotency_key",
            name="uq_workspace_onboardings_activation_idempotency",
        ),
        CheckConstraint(
            "status IN ('draft', 'in_progress', 'ready_for_review', 'active', 'blocked')",
            name="ck_workspace_onboardings_status",
        ),
        CheckConstraint("activation_version >= 0", name="ck_workspace_onboardings_activation_version"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    actor_id: Mapped[str] = mapped_column(String(180), index=True)
    session_id: Mapped[str | None] = mapped_column(String(180), index=True)
    request_id: Mapped[str | None] = mapped_column(String(180), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    business_purpose: Mapped[str] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    required_object_types: Mapped[list] = mapped_column(JSON, default=list)
    validation_gaps: Mapped[list] = mapped_column(JSON, default=list)
    input_versions: Mapped[dict] = mapped_column(JSON, default=dict)
    last_completed_step: Mapped[str | None] = mapped_column(String(120))
    policy_version: Mapped[int | None] = mapped_column(Integer)
    activation_version: Mapped[int] = mapped_column(Integer, default=0)
    activated_by: Mapped[str | None] = mapped_column(String(180))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activation_idempotency_key: Mapped[str | None] = mapped_column(String(180))
    activation_business_purpose: Mapped[str | None] = mapped_column(String(240))
    activation_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)


class ImportJob(TimestampMixin, Base):
    __tablename__ = "import_jobs"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "idempotency_key"),
        UniqueConstraint("workspace_id", "completion_idempotency_key"),
        UniqueConstraint("workspace_id", "cancellation_idempotency_key"),
        UniqueConstraint("workspace_id", "apply_idempotency_key"),
        UniqueConstraint("workspace_id", "compensation_idempotency_key"),
        ForeignKeyConstraint(
            ["workspace_id", "selected_mapping_version_id"],
            ["import_mapping_versions.workspace_id", "import_mapping_versions.id"],
            name="fk_import_jobs_selected_mapping_workspace",
            use_alter=True,
        ),
        ForeignKeyConstraint(
            ["workspace_id", "selected_change_set_id"],
            ["import_change_sets.workspace_id", "import_change_sets.id"],
            name="fk_import_jobs_selected_change_set_workspace",
            use_alter=True,
        ),
        CheckConstraint(
            "status IN ('created', 'uploading', 'uploaded', 'verifying', 'scanning', "
            "'ready_for_mapping', 'mapping', 'validating', 'ready_for_review', 'applying', "
            "'completed', 'partially_completed', 'failed', 'cancelled', 'expired', "
            "'compensating', 'compensated')",
            name="ck_import_jobs_status",
        ),
        CheckConstraint("source_format IN ('csv', 'grovello_json')", name="ck_import_jobs_source_format"),
        CheckConstraint("schema_version > 0", name="ck_import_jobs_schema_version"),
        CheckConstraint(
            "total_rows >= 0 AND valid_rows >= 0 AND invalid_rows >= 0 AND applied_rows >= 0",
            name="ck_import_jobs_row_counts",
        ),
        CheckConstraint(
            "dry_run_plan_hash IS NULL OR dry_run_plan_hash ~ '^[0-9a-f]{64}$'",
            name="ck_import_jobs_dry_run_plan_hash",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    actor_id: Mapped[str] = mapped_column(String(180), index=True)
    session_id: Mapped[str | None] = mapped_column(String(180), index=True)
    request_id: Mapped[str | None] = mapped_column(String(180), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    completion_idempotency_key: Mapped[str | None] = mapped_column(String(180))
    cancellation_idempotency_key: Mapped[str | None] = mapped_column(String(180))
    business_purpose: Mapped[str] = mapped_column(String(240))
    object_type: Mapped[str] = mapped_column(String(40), index=True)
    source_format: Mapped[str] = mapped_column(String(32))
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    locale: Mapped[str] = mapped_column(String(12), default="en")
    status: Mapped[str] = mapped_column(String(32), default="created", index=True)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, default=0)
    applied_rows: Mapped[int] = mapped_column(Integer, default=0)
    dry_run_plan_hash: Mapped[str | None] = mapped_column(String(64))
    workflow_id: Mapped[str | None] = mapped_column(String(180), unique=True, index=True)
    workflow_run_id: Mapped[str | None] = mapped_column(String(180))
    selected_mapping_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    validation_idempotency_key: Mapped[str | None] = mapped_column(String(180))
    validation_business_purpose: Mapped[str | None] = mapped_column(String(240))
    validation_workflow_id: Mapped[str | None] = mapped_column(String(180), unique=True, index=True)
    parser_version: Mapped[str | None] = mapped_column(String(40))
    selected_change_set_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    apply_idempotency_key: Mapped[str | None] = mapped_column(String(180))
    apply_workflow_id: Mapped[str | None] = mapped_column(String(180), unique=True, index=True)
    compensation_idempotency_key: Mapped[str | None] = mapped_column(String(180))
    compensation_workflow_id: Mapped[str | None] = mapped_column(String(180), unique=True, index=True)
    compensation_policy_version: Mapped[int | None] = mapped_column(Integer)
    compensation_business_purpose: Mapped[str | None] = mapped_column(String(240))
    input_versions: Mapped[dict] = mapped_column(JSON, default=dict)
    result_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    failure_code: Mapped[str | None] = mapped_column(String(100))
    failure_detail: Mapped[str | None] = mapped_column(Text)
    retention_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ImportSource(TimestampMixin, Base):
    __tablename__ = "import_sources"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "job_id"),
        UniqueConstraint("workspace_id", "storage_profile", "object_key"),
        ForeignKeyConstraint(
            ["workspace_id", "job_id"],
            ["import_jobs.workspace_id", "import_jobs.id"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "state IN ('uploading', 'uploaded', 'verifying', 'scanning', 'clean', "
            "'quarantined', 'failed', 'cancelled', 'expired', 'deleted')",
            name="ck_import_sources_state",
        ),
        CheckConstraint("declared_size > 0", name="ck_import_sources_declared_size"),
        CheckConstraint("declared_sha256 ~ '^[0-9a-f]{64}$'", name="ck_import_sources_declared_sha256"),
        CheckConstraint(
            "verified_sha256 IS NULL OR verified_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_import_sources_verified_sha256",
        ),
        CheckConstraint(
            "scan_status IN ('not_started', 'pending', 'clean', 'infected', 'failed')",
            name="ck_import_sources_scan_status",
        ),
        CheckConstraint("scan_attempts >= 0", name="ck_import_sources_scan_attempts"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    state: Mapped[str] = mapped_column(String(32), default="uploading", index=True)
    original_filename: Mapped[str] = mapped_column(String(500))
    declared_mime_type: Mapped[str] = mapped_column(String(255))
    declared_size: Mapped[int] = mapped_column(BigInteger)
    declared_sha256: Mapped[str] = mapped_column(String(64))
    storage_profile: Mapped[str] = mapped_column(String(80), default="default")
    object_key: Mapped[str] = mapped_column(String(1024))
    provider_version_id: Mapped[str | None] = mapped_column(String(1024))
    etag: Mapped[str | None] = mapped_column(String(255))
    verified_size: Mapped[int | None] = mapped_column(BigInteger)
    verified_mime_type: Mapped[str | None] = mapped_column(String(255))
    verified_sha256: Mapped[str | None] = mapped_column(String(64))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scan_status: Mapped[str] = mapped_column(String(32), default="not_started", index=True)
    scan_provider: Mapped[str | None] = mapped_column(String(120))
    scan_reference: Mapped[str | None] = mapped_column(String(500))
    scan_attempts: Mapped[int] = mapped_column(Integer, default=0)
    scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quarantine_object_key: Mapped[str | None] = mapped_column(String(1024))
    quarantine_provider_version_id: Mapped[str | None] = mapped_column(String(1024))
    quarantined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    deletion_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ImportMappingVersion(Base):
    __tablename__ = "import_mapping_versions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "job_id", "version"),
        UniqueConstraint("workspace_id", "job_id", "idempotency_key"),
        ForeignKeyConstraint(
            ["workspace_id", "job_id"], ["import_jobs.workspace_id", "import_jobs.id"], ondelete="CASCADE"
        ),
        CheckConstraint("version > 0", name="ck_import_mapping_versions_version"),
        CheckConstraint(
            "schema_fingerprint ~ '^[0-9a-f]{64}$'",
            name="ck_import_mapping_versions_schema_fingerprint",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    version: Mapped[int] = mapped_column(Integer)
    schema_fingerprint: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str | None] = mapped_column(String(180))
    business_purpose: Mapped[str | None] = mapped_column(String(240))
    source_fields: Mapped[list] = mapped_column(JSON, default=list)
    delimiter: Mapped[str | None] = mapped_column(String(4))
    mappings: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ImportRow(Base):
    __tablename__ = "import_rows"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "job_id", "source_row_number"),
        ForeignKeyConstraint(
            ["workspace_id", "job_id"], ["import_jobs.workspace_id", "import_jobs.id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["workspace_id", "mapping_version_id"],
            ["import_mapping_versions.workspace_id", "import_mapping_versions.id"],
        ),
        CheckConstraint("source_row_number > 0", name="ck_import_rows_source_row_number"),
        CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="ck_import_rows_content_hash"),
        CheckConstraint(
            "status IN ('pending', 'valid', 'invalid', 'duplicate', 'conflict', 'planned', "
            "'applied', 'skipped', 'failed', 'compensated')",
            name="ck_import_rows_status",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    mapping_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    source_row_number: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))
    normalized_data: Mapped[dict] = mapped_column(JSON, default=dict)
    target_identity: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    planned_operation: Mapped[str | None] = mapped_column(String(32))
    applied_object_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    applied_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ImportIssue(Base):
    __tablename__ = "import_issues"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        ForeignKeyConstraint(
            ["workspace_id", "job_id"], ["import_jobs.workspace_id", "import_jobs.id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["workspace_id", "row_id"], ["import_rows.workspace_id", "import_rows.id"], ondelete="CASCADE"
        ),
        CheckConstraint("severity IN ('warning', 'error', 'blocking')", name="ck_import_issues_severity"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    row_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    code: Mapped[str] = mapped_column(String(100), index=True)
    severity: Mapped[str] = mapped_column(String(16))
    field_locator: Mapped[dict] = mapped_column(JSON, default=dict)
    message: Mapped[str] = mapped_column(String(500))
    redacted_sample: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ImportChangeSet(Base):
    __tablename__ = "import_change_sets"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "job_id", "version"),
        UniqueConstraint("workspace_id", "plan_hash"),
        UniqueConstraint("workspace_id", "job_id", "idempotency_key"),
        UniqueConstraint("workspace_id", "approval_idempotency_key"),
        ForeignKeyConstraint(
            ["workspace_id", "job_id"], ["import_jobs.workspace_id", "import_jobs.id"], ondelete="CASCADE"
        ),
        CheckConstraint("version > 0", name="ck_import_change_sets_version"),
        CheckConstraint("plan_hash ~ '^[0-9a-f]{64}$'", name="ck_import_change_sets_plan_hash"),
        CheckConstraint(
            "status IN ('draft', 'ready_for_review', 'approved', 'rejected', 'applied', 'superseded')",
            name="ck_import_change_sets_status",
        ),
        CheckConstraint(
            "approval_state IN ('not_required', 'pending', 'approved', 'rejected')",
            name="ck_import_change_sets_approval_state",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    version: Mapped[int] = mapped_column(Integer)
    plan_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    expected_inputs: Mapped[dict] = mapped_column(JSON, default=dict)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    approval_state: Mapped[str] = mapped_column(String(32), default="not_required")
    idempotency_key: Mapped[str] = mapped_column(String(180))
    business_purpose: Mapped[str] = mapped_column(String(240))
    approval_policy_version: Mapped[int | None] = mapped_column(Integer)
    approval_requested_by: Mapped[str | None] = mapped_column(String(180))
    approval_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approval_decided_by: Mapped[str | None] = mapped_column(String(180))
    approval_decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approval_reason: Mapped[str | None] = mapped_column(String(500))
    approval_idempotency_key: Mapped[str | None] = mapped_column(String(180))
    created_by: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ImportChangeSetOperation(Base):
    __tablename__ = "import_change_set_operations"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "change_set_id", "sequence"),
        UniqueConstraint("workspace_id", "operation_key"),
        ForeignKeyConstraint(
            ["workspace_id", "change_set_id"],
            ["import_change_sets.workspace_id", "import_change_sets.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "row_id"],
            ["import_rows.workspace_id", "import_rows.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "target_object_id"],
            ["business_objects.workspace_id", "business_objects.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "expected_version_id"],
            ["business_object_versions.workspace_id", "business_object_versions.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "result_object_id"],
            ["business_objects.workspace_id", "business_objects.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "result_version_id"],
            ["business_object_versions.workspace_id", "business_object_versions.id"],
        ),
        CheckConstraint("sequence > 0", name="ck_import_change_set_operations_sequence"),
        CheckConstraint(
            "operation IN ('create', 'new_version', 'skip', 'conflict')",
            name="ck_import_change_set_operations_operation",
        ),
        CheckConstraint(
            "status IN ('planned', 'applied', 'skipped', 'failed', 'compensated')",
            name="ck_import_change_set_operations_status",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    change_set_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    row_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    operation_key: Mapped[str] = mapped_column(String(180))
    operation: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="planned", index=True)
    target_object_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    expected_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    expected_version: Mapped[int | None] = mapped_column(Integer)
    input_snapshot: Mapped[dict] = mapped_column(JSON)
    result_object_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    result_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    result_version: Mapped[int | None] = mapped_column(Integer)
    compensation_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    failure_code: Mapped[str | None] = mapped_column(String(100))
    failure_detail: Mapped[str | None] = mapped_column(Text)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    compensated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
