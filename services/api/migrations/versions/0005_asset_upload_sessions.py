"""Add governed upload-session execution metadata.

Revision ID: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "asset_upload_sessions",
        sa.Column("business_purpose", sa.String(240), nullable=False, server_default="Asset upload"),
    )
    op.alter_column("asset_upload_sessions", "business_purpose", server_default=None)
    op.add_column("asset_upload_sessions", sa.Column("session_id", sa.String(180)))
    op.add_column("asset_upload_sessions", sa.Column("request_id", sa.String(180)))
    op.add_column("asset_upload_sessions", sa.Column("completion_idempotency_key", sa.String(180)))
    op.add_column("asset_upload_sessions", sa.Column("workflow_id", sa.String(180)))
    op.add_column("asset_upload_sessions", sa.Column("verified_size", sa.BigInteger()))
    op.add_column("asset_upload_sessions", sa.Column("verified_sha256", sa.String(64)))
    op.add_column("asset_upload_sessions", sa.Column("verified_mime_type", sa.String(255)))
    op.add_column("asset_upload_sessions", sa.Column("verified_at", sa.DateTime(timezone=True)))
    op.create_index("ix_asset_upload_sessions_session_id", "asset_upload_sessions", ["session_id"])
    op.create_index("ix_asset_upload_sessions_request_id", "asset_upload_sessions", ["request_id"])
    op.create_index(
        "ix_asset_upload_sessions_workflow_id",
        "asset_upload_sessions",
        ["workflow_id"],
        unique=True,
    )
    op.create_unique_constraint(
        "uq_asset_upload_sessions_workspace_completion_idempotency",
        "asset_upload_sessions",
        ["workspace_id", "completion_idempotency_key"],
    )
    op.create_check_constraint(
        "ck_asset_upload_sessions_verified_size",
        "asset_upload_sessions",
        "verified_size IS NULL OR verified_size > 0",
    )
    op.create_check_constraint(
        "ck_asset_upload_sessions_verified_sha256",
        "asset_upload_sessions",
        "verified_sha256 IS NULL OR verified_sha256 ~ '^[0-9a-f]{64}$'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_asset_upload_sessions_verified_sha256", "asset_upload_sessions", type_="check")
    op.drop_constraint("ck_asset_upload_sessions_verified_size", "asset_upload_sessions", type_="check")
    op.drop_constraint(
        "uq_asset_upload_sessions_workspace_completion_idempotency",
        "asset_upload_sessions",
        type_="unique",
    )
    op.drop_index("ix_asset_upload_sessions_workflow_id", table_name="asset_upload_sessions")
    op.drop_index("ix_asset_upload_sessions_request_id", table_name="asset_upload_sessions")
    op.drop_index("ix_asset_upload_sessions_session_id", table_name="asset_upload_sessions")
    for column in (
        "verified_at",
        "verified_mime_type",
        "verified_sha256",
        "verified_size",
        "workflow_id",
        "completion_idempotency_key",
        "request_id",
        "session_id",
        "business_purpose",
    ):
        op.drop_column("asset_upload_sessions", column)
