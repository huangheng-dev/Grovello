"""Add immutable mapping and validation workflow lineage.

Revision ID: 0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("import_mapping_versions", sa.Column("idempotency_key", sa.String(180), nullable=True))
    op.add_column("import_mapping_versions", sa.Column("business_purpose", sa.String(240), nullable=True))
    op.add_column(
        "import_mapping_versions",
        sa.Column("source_fields", sa.JSON(), server_default="[]", nullable=False),
    )
    op.add_column("import_mapping_versions", sa.Column("delimiter", sa.String(4), nullable=True))
    op.create_unique_constraint(
        "uq_import_mapping_versions_job_idempotency",
        "import_mapping_versions",
        ["workspace_id", "job_id", "idempotency_key"],
    )

    op.add_column(
        "import_jobs",
        sa.Column("selected_mapping_version_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("import_jobs", sa.Column("validation_idempotency_key", sa.String(180), nullable=True))
    op.add_column("import_jobs", sa.Column("validation_business_purpose", sa.String(240), nullable=True))
    op.add_column("import_jobs", sa.Column("validation_workflow_id", sa.String(180), nullable=True))
    op.add_column("import_jobs", sa.Column("parser_version", sa.String(40), nullable=True))
    op.create_foreign_key(
        "fk_import_jobs_selected_mapping_workspace",
        "import_jobs",
        "import_mapping_versions",
        ["workspace_id", "selected_mapping_version_id"],
        ["workspace_id", "id"],
    )
    op.create_index(
        "ix_import_jobs_selected_mapping_version_id",
        "import_jobs",
        ["selected_mapping_version_id"],
    )
    op.create_index(
        "ix_import_jobs_validation_workflow_id",
        "import_jobs",
        ["validation_workflow_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_import_jobs_validation_workflow_id", table_name="import_jobs")
    op.drop_index("ix_import_jobs_selected_mapping_version_id", table_name="import_jobs")
    op.drop_constraint("fk_import_jobs_selected_mapping_workspace", "import_jobs", type_="foreignkey")
    op.drop_column("import_jobs", "parser_version")
    op.drop_column("import_jobs", "validation_workflow_id")
    op.drop_column("import_jobs", "validation_idempotency_key")
    op.drop_column("import_jobs", "validation_business_purpose")
    op.drop_column("import_jobs", "selected_mapping_version_id")

    op.drop_constraint(
        "uq_import_mapping_versions_job_idempotency",
        "import_mapping_versions",
        type_="unique",
    )
    op.drop_column("import_mapping_versions", "delimiter")
    op.drop_column("import_mapping_versions", "source_fields")
    op.drop_column("import_mapping_versions", "idempotency_key")
    op.drop_column("import_mapping_versions", "business_purpose")
