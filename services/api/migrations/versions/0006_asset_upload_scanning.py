"""Add upload-session malware scan and quarantine evidence.

Revision ID: 0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("asset_upload_sessions", sa.Column("verified_provider_version_id", sa.String(1024)))
    op.add_column("asset_upload_sessions", sa.Column("verified_etag", sa.String(255)))
    op.add_column(
        "asset_upload_sessions",
        sa.Column("scan_status", sa.String(32), nullable=False, server_default="not_started"),
    )
    op.add_column("asset_upload_sessions", sa.Column("scan_provider", sa.String(120)))
    op.add_column("asset_upload_sessions", sa.Column("scan_reference", sa.String(500)))
    op.add_column(
        "asset_upload_sessions",
        sa.Column("scan_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("asset_upload_sessions", sa.Column("scanned_at", sa.DateTime(timezone=True)))
    op.add_column("asset_upload_sessions", sa.Column("quarantine_object_key", sa.String(1024)))
    op.add_column("asset_upload_sessions", sa.Column("quarantine_provider_version_id", sa.String(1024)))
    op.add_column("asset_upload_sessions", sa.Column("quarantined_at", sa.DateTime(timezone=True)))
    op.create_index("ix_asset_upload_sessions_scan_status", "asset_upload_sessions", ["scan_status"])
    op.create_check_constraint(
        "ck_asset_upload_sessions_scan_status",
        "asset_upload_sessions",
        "scan_status IN ('not_started', 'pending', 'clean', 'infected', 'failed')",
    )
    op.create_check_constraint(
        "ck_asset_upload_sessions_scan_attempts",
        "asset_upload_sessions",
        "scan_attempts >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_asset_upload_sessions_scan_attempts", "asset_upload_sessions", type_="check")
    op.drop_constraint("ck_asset_upload_sessions_scan_status", "asset_upload_sessions", type_="check")
    op.drop_index("ix_asset_upload_sessions_scan_status", table_name="asset_upload_sessions")
    for column in (
        "quarantined_at",
        "quarantine_provider_version_id",
        "quarantine_object_key",
        "scanned_at",
        "scan_attempts",
        "scan_reference",
        "scan_provider",
        "scan_status",
        "verified_etag",
        "verified_provider_version_id",
    ):
        op.drop_column("asset_upload_sessions", column)
