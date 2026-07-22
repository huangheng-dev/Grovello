"""Add workspace onboarding and governed import foundation.

Revision ID: 0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "workspace_onboardings",
    "import_jobs",
    "import_sources",
    "import_mapping_versions",
    "import_rows",
    "import_issues",
    "import_change_sets",
)

IMPORT_PERMISSIONS = (
    ("workspace.onboarding.read", "Read workspace business-setup status", "R0"),
    ("workspace.onboarding.write", "Create and update workspace business setup", "R1"),
    ("workspace.onboarding.activate", "Activate a governed business profile", "R3"),
    ("business_truth.import.read", "Read governed business-truth import jobs", "R0"),
    ("business_truth.import.create", "Create and upload business-truth imports", "R1"),
    ("business_truth.import.map", "Map and validate business-truth imports", "R1"),
    ("business_truth.import.apply", "Apply an approved import change set", "R2"),
    ("business_truth.import.cancel", "Cancel a business-truth import job", "R1"),
    ("business_truth.import.compensate", "Compensate accepted import changes", "R4"),
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
    op.create_table(
        "workspace_onboardings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _workspace_column(),
        sa.Column("actor_id", sa.String(180), nullable=False),
        sa.Column("session_id", sa.String(180)),
        sa.Column("request_id", sa.String(180)),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("business_purpose", sa.String(240), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("required_object_types", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("validation_gaps", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("input_versions", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("last_completed_step", sa.String(120)),
        sa.Column("policy_version", sa.Integer()),
        sa.Column("activation_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("activated_by", sa.String(180)),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('draft', 'in_progress', 'ready_for_review', 'active', 'blocked')",
            name="ck_workspace_onboardings_status",
        ),
        sa.CheckConstraint(
            "activation_version >= 0", name="ck_workspace_onboardings_activation_version"
        ),
        sa.UniqueConstraint("workspace_id", "id"),
        sa.UniqueConstraint("workspace_id"),
        sa.UniqueConstraint("workspace_id", "idempotency_key"),
    )

    op.create_table(
        "import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _workspace_column(),
        sa.Column("actor_id", sa.String(180), nullable=False),
        sa.Column("session_id", sa.String(180)),
        sa.Column("request_id", sa.String(180)),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("completion_idempotency_key", sa.String(180)),
        sa.Column("cancellation_idempotency_key", sa.String(180)),
        sa.Column("business_purpose", sa.String(240), nullable=False),
        sa.Column("object_type", sa.String(40), nullable=False),
        sa.Column("source_format", sa.String(32), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("locale", sa.String(12), nullable=False, server_default="en"),
        sa.Column("status", sa.String(32), nullable=False, server_default="created"),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invalid_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("applied_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dry_run_plan_hash", sa.String(64)),
        sa.Column("workflow_id", sa.String(180)),
        sa.Column("workflow_run_id", sa.String(180)),
        sa.Column("input_versions", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("result_summary", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("failure_code", sa.String(100)),
        sa.Column("failure_detail", sa.Text()),
        sa.Column("retention_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('created', 'uploading', 'uploaded', 'verifying', 'scanning', "
            "'ready_for_mapping', 'mapping', 'validating', 'ready_for_review', 'applying', "
            "'completed', 'partially_completed', 'failed', 'cancelled', 'expired', "
            "'compensating', 'compensated')",
            name="ck_import_jobs_status",
        ),
        sa.CheckConstraint(
            "source_format IN ('csv', 'grovello_json')", name="ck_import_jobs_source_format"
        ),
        sa.CheckConstraint("schema_version > 0", name="ck_import_jobs_schema_version"),
        sa.CheckConstraint(
            "total_rows >= 0 AND valid_rows >= 0 AND invalid_rows >= 0 AND applied_rows >= 0",
            name="ck_import_jobs_row_counts",
        ),
        sa.CheckConstraint(
            "dry_run_plan_hash IS NULL OR dry_run_plan_hash ~ '^[0-9a-f]{64}$'",
            name="ck_import_jobs_dry_run_plan_hash",
        ),
        sa.UniqueConstraint("workspace_id", "id"),
        sa.UniqueConstraint("workspace_id", "idempotency_key"),
        sa.UniqueConstraint("workspace_id", "completion_idempotency_key"),
        sa.UniqueConstraint("workspace_id", "cancellation_idempotency_key"),
    )

    op.create_table(
        "import_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _workspace_column(),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state", sa.String(32), nullable=False, server_default="uploading"),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("declared_mime_type", sa.String(255), nullable=False),
        sa.Column("declared_size", sa.BigInteger(), nullable=False),
        sa.Column("declared_sha256", sa.String(64), nullable=False),
        sa.Column("storage_profile", sa.String(80), nullable=False, server_default="default"),
        sa.Column("object_key", sa.String(1024), nullable=False),
        sa.Column("provider_version_id", sa.String(1024)),
        sa.Column("etag", sa.String(255)),
        sa.Column("verified_size", sa.BigInteger()),
        sa.Column("verified_mime_type", sa.String(255)),
        sa.Column("verified_sha256", sa.String(64)),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("scan_status", sa.String(32), nullable=False, server_default="not_started"),
        sa.Column("scan_provider", sa.String(120)),
        sa.Column("scan_reference", sa.String(500)),
        sa.Column("scan_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scanned_at", sa.DateTime(timezone=True)),
        sa.Column("quarantine_object_key", sa.String(1024)),
        sa.Column("quarantine_provider_version_id", sa.String(1024)),
        sa.Column("quarantined_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deletion_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["workspace_id", "job_id"],
            ["import_jobs.workspace_id", "import_jobs.id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "state IN ('uploading', 'uploaded', 'verifying', 'scanning', 'clean', "
            "'quarantined', 'failed', 'cancelled', 'expired', 'deleted')",
            name="ck_import_sources_state",
        ),
        sa.CheckConstraint("declared_size > 0", name="ck_import_sources_declared_size"),
        sa.CheckConstraint(
            "declared_sha256 ~ '^[0-9a-f]{64}$'", name="ck_import_sources_declared_sha256"
        ),
        sa.CheckConstraint(
            "verified_sha256 IS NULL OR verified_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_import_sources_verified_sha256",
        ),
        sa.CheckConstraint(
            "scan_status IN ('not_started', 'pending', 'clean', 'infected', 'failed')",
            name="ck_import_sources_scan_status",
        ),
        sa.CheckConstraint("scan_attempts >= 0", name="ck_import_sources_scan_attempts"),
        sa.UniqueConstraint("workspace_id", "id"),
        sa.UniqueConstraint("workspace_id", "job_id"),
        sa.UniqueConstraint("workspace_id", "storage_profile", "object_key"),
    )

    op.create_table(
        "import_mapping_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _workspace_column(),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("schema_fingerprint", sa.String(64), nullable=False),
        sa.Column("mappings", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id", "job_id"],
            ["import_jobs.workspace_id", "import_jobs.id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("version > 0", name="ck_import_mapping_versions_version"),
        sa.CheckConstraint(
            "schema_fingerprint ~ '^[0-9a-f]{64}$'",
            name="ck_import_mapping_versions_schema_fingerprint",
        ),
        sa.UniqueConstraint("workspace_id", "id"),
        sa.UniqueConstraint("workspace_id", "job_id", "version"),
    )

    op.create_table(
        "import_rows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _workspace_column(),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mapping_version_id", postgresql.UUID(as_uuid=True)),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("normalized_data", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("target_identity", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("planned_operation", sa.String(32)),
        sa.Column("applied_object_id", postgresql.UUID(as_uuid=True)),
        sa.Column("applied_version_id", postgresql.UUID(as_uuid=True)),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["workspace_id", "job_id"],
            ["import_jobs.workspace_id", "import_jobs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "mapping_version_id"],
            ["import_mapping_versions.workspace_id", "import_mapping_versions.id"],
        ),
        sa.CheckConstraint("source_row_number > 0", name="ck_import_rows_source_row_number"),
        sa.CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="ck_import_rows_content_hash"),
        sa.CheckConstraint(
            "status IN ('pending', 'valid', 'invalid', 'duplicate', 'conflict', 'planned', "
            "'applied', 'skipped', 'failed', 'compensated')",
            name="ck_import_rows_status",
        ),
        sa.UniqueConstraint("workspace_id", "id"),
        sa.UniqueConstraint("workspace_id", "job_id", "source_row_number"),
    )

    op.create_table(
        "import_issues",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _workspace_column(),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("row_id", postgresql.UUID(as_uuid=True)),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("field_locator", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("redacted_sample", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id", "job_id"],
            ["import_jobs.workspace_id", "import_jobs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "row_id"],
            ["import_rows.workspace_id", "import_rows.id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "severity IN ('warning', 'error', 'blocking')", name="ck_import_issues_severity"
        ),
        sa.UniqueConstraint("workspace_id", "id"),
    )

    op.create_table(
        "import_change_sets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _workspace_column(),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("plan_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("expected_inputs", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("summary", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("approval_state", sa.String(32), nullable=False, server_default="not_required"),
        sa.Column("created_by", sa.String(180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id", "job_id"],
            ["import_jobs.workspace_id", "import_jobs.id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("version > 0", name="ck_import_change_sets_version"),
        sa.CheckConstraint("plan_hash ~ '^[0-9a-f]{64}$'", name="ck_import_change_sets_plan_hash"),
        sa.CheckConstraint(
            "status IN ('draft', 'ready_for_review', 'approved', 'rejected', 'applied', 'superseded')",
            name="ck_import_change_sets_status",
        ),
        sa.CheckConstraint(
            "approval_state IN ('not_required', 'pending', 'approved', 'rejected')",
            name="ck_import_change_sets_approval_state",
        ),
        sa.UniqueConstraint("workspace_id", "id"),
        sa.UniqueConstraint("workspace_id", "job_id", "version"),
        sa.UniqueConstraint("workspace_id", "plan_hash"),
    )

    for table_name in TENANT_TABLES:
        op.create_index(f"ix_{table_name}_workspace_id", table_name, ["workspace_id"])
        op.execute(sa.text(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{table_name}" FORCE ROW LEVEL SECURITY'))
        op.execute(
            sa.text(
                f'CREATE POLICY "{table_name}_workspace_isolation" ON "{table_name}" '
                "USING (workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid) "
                "WITH CHECK (workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid)"
            )
        )

    for table_name, columns in (
        ("workspace_onboardings", ("status", "actor_id", "session_id", "request_id")),
        (
            "import_jobs",
            ("status", "object_type", "actor_id", "session_id", "request_id", "retention_deadline"),
        ),
        ("import_sources", ("job_id", "state", "scan_status", "expires_at", "deletion_deadline")),
        ("import_mapping_versions", ("job_id",)),
        ("import_rows", ("job_id", "mapping_version_id", "status")),
        ("import_issues", ("job_id", "row_id", "code")),
        ("import_change_sets", ("job_id", "status")),
    ):
        for column in columns:
            op.create_index(f"ix_{table_name}_{column}", table_name, [column])
    op.create_index("ix_import_jobs_workflow_id", "import_jobs", ["workflow_id"], unique=True)

    permission_values = ", ".join(
        f"('{key}', '{description}', '{risk_tier}')"
        for key, description, risk_tier in IMPORT_PERMISSIONS
    )
    op.execute(
        sa.text(
            "INSERT INTO permissions (key, description, risk_tier) VALUES "
            f"{permission_values} ON CONFLICT (key) DO NOTHING"
        )
    )


def downgrade() -> None:
    for table_name in reversed(TENANT_TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table_name}_workspace_isolation" ON "{table_name}"'))
        op.execute(sa.text(f'ALTER TABLE "{table_name}" NO FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{table_name}" DISABLE ROW LEVEL SECURITY'))

    for table_name in reversed(TENANT_TABLES):
        op.drop_table(table_name)

    permission_keys = ", ".join(f"'{key}'" for key, _, _ in IMPORT_PERMISSIONS)
    op.execute(sa.text(f"DELETE FROM permissions WHERE key IN ({permission_keys})"))
