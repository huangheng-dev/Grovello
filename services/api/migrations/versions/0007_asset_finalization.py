"""Add durable asset finalization and staging cleanup evidence.

Revision ID: 0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_asset_upload_sessions_state", "asset_upload_sessions", type_="check")
    op.create_check_constraint(
        "ck_asset_upload_sessions_state",
        "asset_upload_sessions",
        "state IN ('initiated', 'uploaded', 'verifying', 'scanning', 'ready_to_finalize', "
        "'finalizing', 'finalized', 'failed', 'expired', 'cancelled', 'quarantined')",
    )
    op.add_column("asset_upload_sessions", sa.Column("finalization_idempotency_key", sa.String(180)))
    op.add_column("asset_upload_sessions", sa.Column("finalization_request_hash", sa.String(64)))
    op.add_column("asset_upload_sessions", sa.Column("finalization_payload", postgresql.JSONB()))
    op.add_column("asset_upload_sessions", sa.Column("finalization_workflow_id", sa.String(180)))
    op.add_column("asset_upload_sessions", sa.Column("finalized_blob_id", postgresql.UUID(as_uuid=True)))
    op.add_column("asset_upload_sessions", sa.Column("finalized_asset_id", postgresql.UUID(as_uuid=True)))
    op.add_column(
        "asset_upload_sessions", sa.Column("finalized_asset_version_id", postgresql.UUID(as_uuid=True))
    )
    op.add_column("asset_upload_sessions", sa.Column("finalized_at", sa.DateTime(timezone=True)))
    op.add_column(
        "asset_upload_sessions",
        sa.Column("staging_cleanup_status", sa.String(32), nullable=False, server_default="not_started"),
    )
    op.add_column("asset_upload_sessions", sa.Column("staging_cleanup_at", sa.DateTime(timezone=True)))
    op.create_unique_constraint(
        "uq_asset_upload_sessions_workspace_finalization_idempotency",
        "asset_upload_sessions",
        ["workspace_id", "finalization_idempotency_key"],
    )
    op.create_check_constraint(
        "ck_asset_upload_sessions_finalization_request_hash",
        "asset_upload_sessions",
        "finalization_request_hash IS NULL OR finalization_request_hash ~ '^[0-9a-f]{64}$'",
    )
    op.create_check_constraint(
        "ck_asset_upload_sessions_staging_cleanup_status",
        "asset_upload_sessions",
        "staging_cleanup_status IN ('not_started', 'pending', 'complete', 'failed')",
    )
    op.create_foreign_key(
        "fk_asset_upload_sessions_finalized_blob",
        "asset_upload_sessions",
        "asset_blobs",
        ["workspace_id", "finalized_blob_id"],
        ["workspace_id", "id"],
    )
    op.create_foreign_key(
        "fk_asset_upload_sessions_finalized_asset",
        "asset_upload_sessions",
        "business_objects",
        ["workspace_id", "finalized_asset_id"],
        ["workspace_id", "id"],
    )
    op.create_foreign_key(
        "fk_asset_upload_sessions_finalized_asset_version",
        "asset_upload_sessions",
        "business_object_versions",
        ["workspace_id", "finalized_asset_version_id"],
        ["workspace_id", "id"],
    )
    op.create_index(
        "ix_asset_upload_sessions_finalization_workflow_id",
        "asset_upload_sessions",
        ["finalization_workflow_id"],
        unique=True,
    )
    op.create_index(
        "ix_asset_upload_sessions_finalized_asset_id",
        "asset_upload_sessions",
        ["finalized_asset_id"],
    )
    op.create_index(
        "ix_asset_upload_sessions_staging_cleanup_status",
        "asset_upload_sessions",
        ["staging_cleanup_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_asset_upload_sessions_staging_cleanup_status", table_name="asset_upload_sessions")
    op.drop_index("ix_asset_upload_sessions_finalized_asset_id", table_name="asset_upload_sessions")
    op.drop_index("ix_asset_upload_sessions_finalization_workflow_id", table_name="asset_upload_sessions")
    op.drop_constraint(
        "fk_asset_upload_sessions_finalized_asset_version", "asset_upload_sessions", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_asset_upload_sessions_finalized_asset", "asset_upload_sessions", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_asset_upload_sessions_finalized_blob", "asset_upload_sessions", type_="foreignkey"
    )
    op.drop_constraint(
        "ck_asset_upload_sessions_staging_cleanup_status", "asset_upload_sessions", type_="check"
    )
    op.drop_constraint(
        "ck_asset_upload_sessions_finalization_request_hash", "asset_upload_sessions", type_="check"
    )
    op.drop_constraint(
        "uq_asset_upload_sessions_workspace_finalization_idempotency",
        "asset_upload_sessions",
        type_="unique",
    )
    for column in (
        "staging_cleanup_at",
        "staging_cleanup_status",
        "finalized_at",
        "finalized_asset_version_id",
        "finalized_asset_id",
        "finalized_blob_id",
        "finalization_workflow_id",
        "finalization_payload",
        "finalization_request_hash",
        "finalization_idempotency_key",
    ):
        op.drop_column("asset_upload_sessions", column)
    op.drop_constraint("ck_asset_upload_sessions_state", "asset_upload_sessions", type_="check")
    op.create_check_constraint(
        "ck_asset_upload_sessions_state",
        "asset_upload_sessions",
        "state IN ('initiated', 'uploaded', 'verifying', 'scanning', 'ready_to_finalize', "
        "'finalized', 'failed', 'expired', 'cancelled', 'quarantined')",
    )
