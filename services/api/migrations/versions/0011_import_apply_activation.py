"""Add governed import apply, approval, compensation, and activation lineage.

Revision ID: 0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("workspace_onboardings", sa.Column("activation_idempotency_key", sa.String(180)))
    op.add_column("workspace_onboardings", sa.Column("activation_business_purpose", sa.String(240)))
    op.add_column(
        "workspace_onboardings",
        sa.Column("activation_snapshot", sa.JSON(), server_default="{}", nullable=False),
    )
    op.create_unique_constraint(
        "uq_workspace_onboardings_activation_idempotency",
        "workspace_onboardings",
        ["workspace_id", "activation_idempotency_key"],
    )

    for name in ("apply_idempotency_key", "compensation_idempotency_key"):
        op.add_column("import_jobs", sa.Column(name, sa.String(180)))
        op.create_unique_constraint(
            f"uq_import_jobs_{name}", "import_jobs", ["workspace_id", name]
        )
    op.add_column(
        "import_jobs", sa.Column("selected_change_set_id", postgresql.UUID(as_uuid=True))
    )
    op.create_index(
        "ix_import_jobs_selected_change_set_id",
        "import_jobs",
        ["selected_change_set_id"],
    )
    op.create_foreign_key(
        "fk_import_jobs_selected_change_set_workspace",
        "import_jobs",
        "import_change_sets",
        ["workspace_id", "selected_change_set_id"],
        ["workspace_id", "id"],
    )
    for name in ("apply_workflow_id", "compensation_workflow_id"):
        op.add_column("import_jobs", sa.Column(name, sa.String(180)))
        op.create_index(f"ix_import_jobs_{name}", "import_jobs", [name], unique=True)
    op.add_column("import_jobs", sa.Column("compensation_policy_version", sa.Integer()))
    op.add_column("import_jobs", sa.Column("compensation_business_purpose", sa.String(240)))

    op.add_column("import_change_sets", sa.Column("idempotency_key", sa.String(180)))
    op.add_column("import_change_sets", sa.Column("business_purpose", sa.String(240)))
    op.add_column("import_change_sets", sa.Column("approval_policy_version", sa.Integer()))
    op.add_column("import_change_sets", sa.Column("approval_requested_by", sa.String(180)))
    op.add_column(
        "import_change_sets", sa.Column("approval_requested_at", sa.DateTime(timezone=True))
    )
    op.add_column("import_change_sets", sa.Column("approval_decided_by", sa.String(180)))
    op.add_column(
        "import_change_sets", sa.Column("approval_decided_at", sa.DateTime(timezone=True))
    )
    op.add_column("import_change_sets", sa.Column("approval_reason", sa.String(500)))
    op.add_column("import_change_sets", sa.Column("approval_idempotency_key", sa.String(180)))
    op.create_unique_constraint(
        "uq_import_change_sets_approval_idempotency",
        "import_change_sets",
        ["workspace_id", "approval_idempotency_key"],
    )
    op.create_unique_constraint(
        "uq_import_change_sets_job_idempotency",
        "import_change_sets",
        ["workspace_id", "job_id", "idempotency_key"],
    )
    op.execute(
        sa.text(
            "UPDATE import_change_sets SET "
            "idempotency_key = 'legacy-change-set-' || id::text, "
            "business_purpose = 'Preserve pre-P2-D3 import review lineage' "
            "WHERE idempotency_key IS NULL OR business_purpose IS NULL"
        )
    )

    op.create_table(
        "import_change_set_operations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("change_set_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("row_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("operation_key", sa.String(180), nullable=False),
        sa.Column("operation", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="planned"),
        sa.Column("target_object_id", postgresql.UUID(as_uuid=True)),
        sa.Column("expected_version_id", postgresql.UUID(as_uuid=True)),
        sa.Column("expected_version", sa.Integer()),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("result_object_id", postgresql.UUID(as_uuid=True)),
        sa.Column("result_version_id", postgresql.UUID(as_uuid=True)),
        sa.Column("result_version", sa.Integer()),
        sa.Column("compensation_snapshot", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("failure_code", sa.String(100)),
        sa.Column("failure_detail", sa.Text()),
        sa.Column("applied_at", sa.DateTime(timezone=True)),
        sa.Column("compensated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id", "change_set_id"],
            ["import_change_sets.workspace_id", "import_change_sets.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "row_id"],
            ["import_rows.workspace_id", "import_rows.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "target_object_id"],
            ["business_objects.workspace_id", "business_objects.id"],
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "expected_version_id"],
            ["business_object_versions.workspace_id", "business_object_versions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "result_object_id"],
            ["business_objects.workspace_id", "business_objects.id"],
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "result_version_id"],
            ["business_object_versions.workspace_id", "business_object_versions.id"],
        ),
        sa.CheckConstraint("sequence > 0", name="ck_import_change_set_operations_sequence"),
        sa.CheckConstraint(
            "operation IN ('create', 'new_version', 'skip', 'conflict')",
            name="ck_import_change_set_operations_operation",
        ),
        sa.CheckConstraint(
            "status IN ('planned', 'applied', 'skipped', 'failed', 'compensated')",
            name="ck_import_change_set_operations_status",
        ),
        sa.UniqueConstraint("workspace_id", "id"),
        sa.UniqueConstraint("workspace_id", "change_set_id", "sequence"),
        sa.UniqueConstraint("workspace_id", "operation_key"),
    )
    for column in ("workspace_id", "change_set_id", "row_id", "status"):
        op.create_index(
            f"ix_import_change_set_operations_{column}",
            "import_change_set_operations",
            [column],
        )
    op.execute(sa.text('ALTER TABLE "import_change_set_operations" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text('ALTER TABLE "import_change_set_operations" FORCE ROW LEVEL SECURITY'))
    op.execute(
        sa.text(
            'CREATE POLICY "import_change_set_operations_workspace_isolation" '
            'ON "import_change_set_operations" '
            "USING (workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid) "
            "WITH CHECK (workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid)"
        )
    )

    op.alter_column("import_change_sets", "idempotency_key", nullable=False)
    op.alter_column("import_change_sets", "business_purpose", nullable=False)


def downgrade() -> None:
    op.execute(
        sa.text(
            'DROP POLICY IF EXISTS "import_change_set_operations_workspace_isolation" '
            'ON "import_change_set_operations"'
        )
    )
    op.execute(sa.text('ALTER TABLE "import_change_set_operations" NO FORCE ROW LEVEL SECURITY'))
    op.execute(sa.text('ALTER TABLE "import_change_set_operations" DISABLE ROW LEVEL SECURITY'))
    op.drop_table("import_change_set_operations")

    op.drop_constraint(
        "uq_import_change_sets_job_idempotency", "import_change_sets", type_="unique"
    )
    op.drop_constraint(
        "uq_import_change_sets_approval_idempotency", "import_change_sets", type_="unique"
    )
    for name in (
        "approval_reason",
        "approval_idempotency_key",
        "approval_decided_at",
        "approval_decided_by",
        "approval_requested_at",
        "approval_requested_by",
        "approval_policy_version",
        "business_purpose",
        "idempotency_key",
    ):
        op.drop_column("import_change_sets", name)

    for name in ("compensation_workflow_id", "apply_workflow_id"):
        op.drop_index(f"ix_import_jobs_{name}", table_name="import_jobs")
        op.drop_column("import_jobs", name)
    op.drop_column("import_jobs", "compensation_business_purpose")
    op.drop_column("import_jobs", "compensation_policy_version")
    op.drop_constraint(
        "fk_import_jobs_selected_change_set_workspace", "import_jobs", type_="foreignkey"
    )
    op.drop_index("ix_import_jobs_selected_change_set_id", table_name="import_jobs")
    op.drop_column("import_jobs", "selected_change_set_id")
    for name in ("compensation_idempotency_key", "apply_idempotency_key"):
        op.drop_constraint(f"uq_import_jobs_{name}", "import_jobs", type_="unique")
        op.drop_column("import_jobs", name)

    op.drop_constraint(
        "uq_workspace_onboardings_activation_idempotency",
        "workspace_onboardings",
        type_="unique",
    )
    op.drop_column("workspace_onboardings", "activation_snapshot")
    op.drop_column("workspace_onboardings", "activation_business_purpose")
    op.drop_column("workspace_onboardings", "activation_idempotency_key")
