"""Add governed asset storage foundation.

Revision ID: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "asset_upload_sessions",
    "asset_blobs",
    "asset_version_files",
)

ASSET_PERMISSIONS = (
    ("asset.read", "Read asset metadata", "R0"),
    ("asset.download", "Download approved asset binaries", "R1"),
    ("asset.write", "Create uploads and version asset metadata", "R1"),
    ("asset.approve", "Approve assets for governed use", "R2"),
    ("asset.archive", "Archive assets", "R2"),
    ("asset.purge", "Permanently purge asset binaries", "R4"),
)


def upgrade() -> None:
    op.create_table(
        "asset_upload_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_asset_id", postgresql.UUID(as_uuid=True)),
        sa.Column("actor_id", sa.String(180), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("declared_mime_type", sa.String(255), nullable=False),
        sa.Column("declared_size", sa.BigInteger(), nullable=False),
        sa.Column("declared_sha256", sa.String(64)),
        sa.Column("staging_object_key", sa.String(1024), nullable=False),
        sa.Column("multipart_upload_id", sa.String(1024)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("failure_code", sa.String(100)),
        sa.Column("failure_detail", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id", "target_asset_id"],
            ["business_objects.workspace_id", "business_objects.id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "state IN ('initiated', 'uploaded', 'verifying', 'scanning', "
            "'ready_to_finalize', 'finalized', 'failed', 'expired', 'cancelled', 'quarantined')",
            name="ck_asset_upload_sessions_state",
        ),
        sa.CheckConstraint(
            "declared_size > 0",
            name="ck_asset_upload_sessions_declared_size",
        ),
        sa.CheckConstraint(
            "declared_sha256 IS NULL OR declared_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_asset_upload_sessions_declared_sha256",
        ),
        sa.UniqueConstraint("workspace_id", "id"),
        sa.UniqueConstraint("workspace_id", "idempotency_key"),
        sa.UniqueConstraint("workspace_id", "staging_object_key"),
    )
    op.create_index("ix_asset_upload_sessions_workspace_id", "asset_upload_sessions", ["workspace_id"])
    op.create_index("ix_asset_upload_sessions_target_asset_id", "asset_upload_sessions", ["target_asset_id"])
    op.create_index("ix_asset_upload_sessions_actor_id", "asset_upload_sessions", ["actor_id"])
    op.create_index("ix_asset_upload_sessions_state", "asset_upload_sessions", ["state"])
    op.create_index("ix_asset_upload_sessions_expires_at", "asset_upload_sessions", ["expires_at"])

    op.create_table(
        "asset_blobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("storage_profile", sa.String(80), nullable=False),
        sa.Column("object_key", sa.String(1024), nullable=False),
        sa.Column("provider_version_id", sa.String(1024)),
        sa.Column("etag", sa.String(255)),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("detected_mime_type", sa.String(255), nullable=False),
        sa.Column("scan_status", sa.String(32), nullable=False),
        sa.Column("scan_provider", sa.String(120)),
        sa.Column("scan_reference", sa.String(500)),
        sa.Column("storage_status", sa.String(32), nullable=False),
        sa.Column("encryption_mode", sa.String(32), nullable=False),
        sa.Column("encryption_key_ref", sa.String(500)),
        sa.Column("retained_until", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("byte_size > 0", name="ck_asset_blobs_byte_size"),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_asset_blobs_sha256"),
        sa.CheckConstraint(
            "scan_status IN ('pending', 'clean', 'infected', 'failed')",
            name="ck_asset_blobs_scan_status",
        ),
        sa.CheckConstraint(
            "storage_status IN ('available', 'quarantined', 'purge_pending', 'purged')",
            name="ck_asset_blobs_storage_status",
        ),
        sa.UniqueConstraint("workspace_id", "id"),
        sa.UniqueConstraint("workspace_id", "storage_profile", "object_key"),
    )
    op.create_index("ix_asset_blobs_workspace_id", "asset_blobs", ["workspace_id"])
    op.create_index("ix_asset_blobs_sha256", "asset_blobs", ["sha256"])
    op.create_index("ix_asset_blobs_scan_status", "asset_blobs", ["scan_status"])
    op.create_index("ix_asset_blobs_storage_status", "asset_blobs", ["storage_status"])
    op.create_index("ix_asset_blobs_retained_until", "asset_blobs", ["retained_until"])
    op.create_index("ix_asset_blobs_deleted_at", "asset_blobs", ["deleted_at"])

    op.create_table(
        "asset_version_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("business_object_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("blob_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("variant_key", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id", "business_object_version_id"],
            ["business_object_versions.workspace_id", "business_object_versions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "blob_id"],
            ["asset_blobs.workspace_id", "asset_blobs.id"],
        ),
        sa.CheckConstraint(
            "role IN ('original', 'thumbnail', 'preview', 'transcript', 'caption')",
            name="ck_asset_version_files_role",
        ),
        sa.UniqueConstraint("workspace_id", "id"),
        sa.UniqueConstraint("workspace_id", "business_object_version_id", "role", "variant_key"),
    )
    op.create_index("ix_asset_version_files_workspace_id", "asset_version_files", ["workspace_id"])
    op.create_index(
        "ix_asset_version_files_business_object_version_id",
        "asset_version_files",
        ["business_object_version_id"],
    )
    op.create_index("ix_asset_version_files_blob_id", "asset_version_files", ["blob_id"])

    permission_values = ", ".join(
        f"('{key}', '{description}', '{risk_tier}')"
        for key, description, risk_tier in ASSET_PERMISSIONS
    )
    op.execute(
        sa.text(
            "INSERT INTO permissions (key, description, risk_tier) VALUES "
            f"{permission_values} ON CONFLICT (key) DO NOTHING"
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

    op.drop_table("asset_version_files")
    op.drop_table("asset_blobs")
    op.drop_table("asset_upload_sessions")
    permission_keys = ", ".join(f"'{key}'" for key, _, _ in ASSET_PERMISSIONS)
    op.execute(sa.text(f"DELETE FROM permissions WHERE key IN ({permission_keys})"))
