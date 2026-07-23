"""Add governed knowledge-ingestion contracts and pipeline-only chunk lineage.

Revision ID: 0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "knowledge_ingestions",
    "knowledge_source_snapshots",
    "knowledge_generations",
    "knowledge_generation_chunks",
    "knowledge_retrieval_receipts",
)

KNOWLEDGE_PERMISSIONS = (
    ("knowledge.retrieve", "Run bounded authorized knowledge retrieval", "R0"),
    ("knowledge.ingest", "Ingest an approved knowledge source version", "R1"),
    ("knowledge.reindex", "Create a new knowledge generation", "R1"),
    ("knowledge.cancel", "Cancel a governed knowledge ingestion", "R1"),
    ("knowledge.retire", "Retire an active knowledge generation", "R2"),
    ("knowledge.sensitive.read", "Read policy-authorized sensitive knowledge", "R2"),
    ("knowledge.admin", "Manage knowledge pipeline and model profiles", "R2"),
)


def _workspace_column() -> sa.Column:
    return sa.Column(
        "workspace_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def upgrade() -> None:
    op.drop_constraint(
        "ck_business_object_versions_source_type",
        "business_object_versions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_business_object_versions_source_type",
        "business_object_versions",
        "source_type IN ('owner_edit', 'import', 'seed', 'pipeline')",
    )
    op.create_unique_constraint(
        "uq_business_object_versions_workspace_object_id_id",
        "business_object_versions",
        ["workspace_id", "object_id", "id"],
    )

    op.create_table(
        "knowledge_ingestions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _workspace_column(),
        sa.Column("source_object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_object_type", sa.String(40), nullable=False),
        sa.Column("actor_id", sa.String(180), nullable=False),
        sa.Column("session_id", sa.String(180)),
        sa.Column("request_id", sa.String(180)),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("business_purpose", sa.String(240), nullable=False),
        sa.Column("pipeline_profile", sa.String(120), nullable=False),
        sa.Column("pipeline_version", sa.String(80), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("input_versions", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("approval_policy_version", sa.Integer()),
        sa.Column("workflow_id", sa.String(180)),
        sa.Column("workflow_run_id", sa.String(180)),
        sa.Column("cost_summary", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("failure_code", sa.String(100)),
        sa.Column("failure_detail", sa.Text()),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["workspace_id", "source_object_id"],
            ["business_objects.workspace_id", "business_objects.id"],
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "source_object_id", "source_version_id"],
            [
                "business_object_versions.workspace_id",
                "business_object_versions.object_id",
                "business_object_versions.id",
            ],
        ),
        sa.CheckConstraint(
            "source_object_type IN ('knowledge_document', 'evidence', 'case_study', 'asset')",
            name="ck_knowledge_ingestions_source_object_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'ready', 'failed', 'cancelled')",
            name="ck_knowledge_ingestions_status",
        ),
        sa.CheckConstraint(
            "request_hash ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_ingestions_request_hash",
        ),
        sa.CheckConstraint(
            "approval_policy_version IS NULL OR approval_policy_version > 0",
            name="ck_knowledge_ingestions_policy_version",
        ),
        sa.UniqueConstraint("workspace_id", "id"),
        sa.UniqueConstraint("workspace_id", "idempotency_key"),
        sa.UniqueConstraint("workflow_id"),
    )
    for column in (
        "workspace_id",
        "source_object_id",
        "source_version_id",
        "actor_id",
        "status",
        "workflow_id",
    ):
        op.create_index(
            f"ix_knowledge_ingestions_{column}",
            "knowledge_ingestions",
            [column],
        )

    op.create_table(
        "knowledge_source_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _workspace_column(),
        sa.Column("ingestion_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_object_type", sa.String(40), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("locale", sa.String(12), nullable=False),
        sa.Column("source_status", sa.String(32), nullable=False),
        sa.Column("usage_rights", sa.String(64), nullable=False),
        sa.Column("sensitivity", sa.String(32), nullable=False),
        sa.Column("parser_eligible", sa.Boolean(), nullable=False),
        sa.Column("source_locator", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("source_metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("policy_version", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id", "ingestion_id"],
            ["knowledge_ingestions.workspace_id", "knowledge_ingestions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "source_object_id"],
            ["business_objects.workspace_id", "business_objects.id"],
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "source_object_id", "source_version_id"],
            [
                "business_object_versions.workspace_id",
                "business_object_versions.object_id",
                "business_object_versions.id",
            ],
        ),
        sa.CheckConstraint(
            "source_object_type IN ('knowledge_document', 'evidence', 'case_study', 'asset')",
            name="ck_knowledge_source_snapshots_source_object_type",
        ),
        sa.CheckConstraint(
            "content_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_source_snapshots_content_sha256",
        ),
        sa.CheckConstraint(
            "policy_version IS NULL OR policy_version > 0",
            name="ck_knowledge_source_snapshots_policy_version",
        ),
        sa.UniqueConstraint("workspace_id", "id"),
        sa.UniqueConstraint("workspace_id", "ingestion_id"),
    )
    for column in ("workspace_id", "ingestion_id", "source_object_id", "source_version_id"):
        op.create_index(
            f"ix_knowledge_source_snapshots_{column}",
            "knowledge_source_snapshots",
            [column],
        )

    op.create_table(
        "knowledge_generations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _workspace_column(),
        sa.Column("ingestion_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("pipeline_profile", sa.String(120), nullable=False),
        sa.Column("pipeline_version", sa.String(80), nullable=False),
        sa.Column("parser_profile", sa.String(120), nullable=False, server_default="canonical-json-v1"),
        sa.Column("normalizer_version", sa.String(80), nullable=False, server_default="none"),
        sa.Column("classifier_version", sa.String(80), nullable=False, server_default="none"),
        sa.Column("chunker_version", sa.String(80), nullable=False, server_default="none"),
        sa.Column("embedding_config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warnings", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("retired_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["workspace_id", "ingestion_id"],
            ["knowledge_ingestions.workspace_id", "knowledge_ingestions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "source_snapshot_id"],
            ["knowledge_source_snapshots.workspace_id", "knowledge_source_snapshots.id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'building', 'staged', 'active', 'retired', 'failed')",
            name="ck_knowledge_generations_status",
        ),
        sa.CheckConstraint("chunk_count >= 0", name="ck_knowledge_generations_chunk_count"),
        sa.UniqueConstraint("workspace_id", "id"),
        sa.UniqueConstraint("workspace_id", "ingestion_id"),
    )
    for column in ("workspace_id", "ingestion_id", "source_snapshot_id", "status"):
        op.create_index(
            f"ix_knowledge_generations_{column}",
            "knowledge_generations",
            [column],
        )

    op.create_table(
        "knowledge_generation_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _workspace_column(),
        sa.Column("generation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id", "generation_id"],
            ["knowledge_generations.workspace_id", "knowledge_generations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "chunk_object_id"],
            ["business_objects.workspace_id", "business_objects.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "chunk_object_id", "chunk_version_id"],
            [
                "business_object_versions.workspace_id",
                "business_object_versions.object_id",
                "business_object_versions.id",
            ],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("ordinal > 0", name="ck_knowledge_generation_chunks_ordinal"),
        sa.CheckConstraint(
            "content_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_generation_chunks_content_sha256",
        ),
        sa.UniqueConstraint("workspace_id", "id"),
        sa.UniqueConstraint("workspace_id", "generation_id", "ordinal"),
        sa.UniqueConstraint("workspace_id", "chunk_version_id"),
    )
    for column in ("workspace_id", "generation_id", "chunk_object_id", "chunk_version_id"):
        op.create_index(
            f"ix_knowledge_generation_chunks_{column}",
            "knowledge_generation_chunks",
            [column],
        )

    op.create_table(
        "knowledge_retrieval_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _workspace_column(),
        sa.Column("actor_id", sa.String(180), nullable=False),
        sa.Column("session_id", sa.String(180)),
        sa.Column("request_id", sa.String(180)),
        sa.Column("business_purpose", sa.String(240), nullable=False),
        sa.Column("query_hash", sa.String(64), nullable=False),
        sa.Column("query_metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("filters", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("policy_version", sa.Integer()),
        sa.Column("lexical_config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("vector_config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("semantic_status", sa.String(32), nullable=False, server_default="unavailable"),
        sa.Column("result_chunk_version_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("score_components", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "query_hash ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_retrieval_receipts_query_hash",
        ),
        sa.CheckConstraint(
            "semantic_status IN ('unavailable', 'available', 'degraded')",
            name="ck_knowledge_retrieval_receipts_semantic_status",
        ),
        sa.CheckConstraint(
            "policy_version IS NULL OR policy_version > 0",
            name="ck_knowledge_retrieval_receipts_policy_version",
        ),
        sa.CheckConstraint("result_count >= 0", name="ck_knowledge_retrieval_receipts_result_count"),
        sa.CheckConstraint("latency_ms >= 0", name="ck_knowledge_retrieval_receipts_latency_ms"),
        sa.UniqueConstraint("workspace_id", "id"),
    )
    for column in ("workspace_id", "actor_id", "query_hash", "created_at"):
        op.create_index(
            f"ix_knowledge_retrieval_receipts_{column}",
            "knowledge_retrieval_receipts",
            [column],
        )

    for table_name in TENANT_TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{table_name}" FORCE ROW LEVEL SECURITY'))
        op.execute(
            sa.text(
                f'CREATE POLICY "{table_name}_workspace_isolation" ON "{table_name}" '
                "USING (workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid) "
                "WITH CHECK (workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid)"
            )
        )

    permission_values = ", ".join(
        f"('{key}', '{description}', '{risk_tier}')"
        for key, description, risk_tier in KNOWLEDGE_PERMISSIONS
    )
    op.execute(
        sa.text(
            "INSERT INTO permissions (key, description, risk_tier) VALUES "
            f"{permission_values} ON CONFLICT (key) DO NOTHING"
        )
    )


def downgrade() -> None:
    for table_name in reversed(TENANT_TABLES):
        op.execute(
            sa.text(
                f'DROP POLICY IF EXISTS "{table_name}_workspace_isolation" ON "{table_name}"'
            )
        )
        op.execute(sa.text(f'ALTER TABLE "{table_name}" NO FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{table_name}" DISABLE ROW LEVEL SECURITY'))

    for table_name in reversed(TENANT_TABLES):
        op.drop_table(table_name)

    op.execute(
        sa.text(
            "DELETE FROM business_objects AS object "
            "WHERE object.object_type = 'knowledge_chunk' AND EXISTS ("
            "SELECT 1 FROM business_object_versions AS version "
            "WHERE version.workspace_id = object.workspace_id "
            "AND version.object_id = object.id "
            "AND version.source_type = 'pipeline'"
            ")"
        )
    )
    op.drop_constraint(
        "uq_business_object_versions_workspace_object_id_id",
        "business_object_versions",
        type_="unique",
    )
    op.drop_constraint(
        "ck_business_object_versions_source_type",
        "business_object_versions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_business_object_versions_source_type",
        "business_object_versions",
        "source_type IN ('owner_edit', 'import', 'seed')",
    )

    permission_keys = ", ".join(f"'{key}'" for key, _, _ in KNOWLEDGE_PERMISSIONS)
    op.execute(sa.text(f"DELETE FROM permissions WHERE key IN ({permission_keys})"))
