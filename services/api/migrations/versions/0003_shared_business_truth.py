"""Add versioned shared business truth and evidence citations.

Revision ID: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "business_objects",
    "business_object_versions",
    "business_truth_citations",
)


def upgrade() -> None:
    op.create_table(
        "business_objects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("object_type", sa.String(40), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "object_type IN ('brand', 'product', 'offer', 'price_book', 'market', 'icp', "
            "'evidence', 'knowledge_document', 'knowledge_chunk', 'asset', 'case_study')",
            name="ck_business_objects_object_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'archived')",
            name="ck_business_objects_status",
        ),
        sa.UniqueConstraint("workspace_id", "id"),
        sa.UniqueConstraint("workspace_id", "object_type", "slug"),
    )
    op.create_index("ix_business_objects_workspace_id", "business_objects", ["workspace_id"])
    op.create_index("ix_business_objects_object_type", "business_objects", ["object_type"])

    op.create_table(
        "business_object_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("locale", sa.String(12), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("business_purpose", sa.String(240), nullable=False),
        sa.Column("actor_id", sa.String(180), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_ref", sa.String(500)),
        sa.Column("change_summary", sa.String(500), nullable=False),
        sa.Column("input_versions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_business_object_versions_version"),
        sa.CheckConstraint("schema_version > 0", name="ck_business_object_versions_schema_version"),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'archived')",
            name="ck_business_object_versions_status",
        ),
        sa.CheckConstraint(
            "source_type IN ('owner_edit', 'import', 'seed')",
            name="ck_business_object_versions_source_type",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "object_id"],
            ["business_objects.workspace_id", "business_objects.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("workspace_id", "id"),
        sa.UniqueConstraint("workspace_id", "object_id", "version"),
        sa.UniqueConstraint("workspace_id", "idempotency_key"),
    )
    op.create_index(
        "ix_business_object_versions_workspace_id",
        "business_object_versions",
        ["workspace_id"],
    )
    op.create_index(
        "ix_business_object_versions_object_id",
        "business_object_versions",
        ["object_id"],
    )
    op.create_index(
        "ix_business_object_versions_actor_id",
        "business_object_versions",
        ["actor_id"],
    )

    op.create_table(
        "business_truth_citations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("citing_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("locator", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id", "citing_version_id"],
            ["business_object_versions.workspace_id", "business_object_versions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "evidence_version_id"],
            ["business_object_versions.workspace_id", "business_object_versions.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("workspace_id", "id"),
    )
    op.create_index(
        "ix_business_truth_citations_workspace_id",
        "business_truth_citations",
        ["workspace_id"],
    )
    op.create_index(
        "ix_business_truth_citations_citing_version_id",
        "business_truth_citations",
        ["citing_version_id"],
    )
    op.create_index(
        "ix_business_truth_citations_evidence_version_id",
        "business_truth_citations",
        ["evidence_version_id"],
    )

    op.execute(
        sa.text(
            """
            INSERT INTO permissions (key, description, risk_tier)
            VALUES
              ('business_truth.read', 'Read versioned shared business truth', 'R0'),
              ('business_truth.write', 'Create and version shared business truth', 'R1')
            ON CONFLICT (key) DO NOTHING
            """
        )
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


def downgrade() -> None:
    for table_name in reversed(TENANT_TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table_name}_workspace_isolation" ON "{table_name}"'))
        op.execute(sa.text(f'ALTER TABLE "{table_name}" NO FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{table_name}" DISABLE ROW LEVEL SECURITY'))

    op.drop_table("business_truth_citations")
    op.drop_table("business_object_versions")
    op.drop_table("business_objects")
    op.execute(
        sa.text("DELETE FROM permissions WHERE key IN ('business_truth.read', 'business_truth.write')")
    )
