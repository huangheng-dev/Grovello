"""Add organization, access control, sessions, and tenant RLS.

Revision ID: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_ORGANIZATION_ID = "00000000-0000-4000-8000-000000001001"

TENANT_TABLES = (
    "workspaces",
    "goals",
    "runs",
    "audit_events",
    "outbox_events",
    "teams",
    "workspace_memberships",
    "roles",
    "role_permissions",
    "membership_roles",
    "policies",
    "user_sessions",
)


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"])
    op.execute(
        sa.text(
            """
            INSERT INTO organizations (id, slug, name, status)
            VALUES (CAST(:id AS uuid), 'northstar-industrial', 'Northstar Industrial', 'active')
            ON CONFLICT (id) DO NOTHING
            """
        ).bindparams(id=LEGACY_ORGANIZATION_ID)
    )

    op.add_column("workspaces", sa.Column("organization_id", postgresql.UUID(as_uuid=True)))
    op.add_column("workspaces", sa.Column("currency", sa.String(3), server_default="USD"))
    op.execute(
        sa.text(
            "UPDATE workspaces SET organization_id = CAST(:id AS uuid) WHERE organization_id IS NULL"
        ).bindparams(id=LEGACY_ORGANIZATION_ID)
    )
    op.alter_column("workspaces", "organization_id", nullable=False)
    op.alter_column("workspaces", "currency", nullable=False, server_default=None)
    op.create_foreign_key(
        "fk_workspaces_organization_id",
        "workspaces",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_workspaces_organization_id", "workspaces", ["organization_id"])

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_subject", sa.String(255), nullable=False, unique=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_organization_id", "users", ["organization_id"])
    op.create_index("ix_users_external_subject", "users", ["external_subject"])
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "teams",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workspace_id", "slug"),
    )
    op.create_index("ix_teams_workspace_id", "teams", ["workspace_id"])

    op.create_table(
        "workspace_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workspace_id", "user_id"),
    )
    op.create_index("ix_workspace_memberships_workspace_id", "workspace_memberships", ["workspace_id"])
    op.create_index("ix_workspace_memberships_user_id", "workspace_memberships", ["user_id"])

    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workspace_id", "key"),
    )
    op.create_index("ix_roles_workspace_id", "roles", ["workspace_id"])

    op.create_table(
        "permissions",
        sa.Column("key", sa.String(160), primary_key=True),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("risk_tier", sa.String(2), nullable=False),
    )
    op.create_table(
        "role_permissions",
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "permission_key",
            sa.String(160),
            sa.ForeignKey("permissions.key", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_table(
        "membership_roles",
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "membership_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspace_memberships.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_table(
        "policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workspace_id", "key", "version"),
    )
    op.create_index("ix_policies_workspace_id", "policies", ["workspace_id"])

    op.create_table(
        "user_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("identity_provider", sa.String(80), nullable=False),
        sa.Column("provider_session_id_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_user_sessions_workspace_id", "user_sessions", ["workspace_id"])
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"])
    op.create_index("ix_user_sessions_revoked_at", "user_sessions", ["revoked_at"])

    op.add_column("audit_events", sa.Column("session_id", sa.String(180)))
    op.add_column("audit_events", sa.Column("request_id", sa.String(180)))
    op.add_column("audit_events", sa.Column("outcome", sa.String(32), server_default="succeeded"))
    op.alter_column("audit_events", "outcome", nullable=False, server_default=None)
    op.create_index("ix_audit_events_session_id", "audit_events", ["session_id"])
    op.create_index("ix_audit_events_request_id", "audit_events", ["request_id"])

    for table_name in TENANT_TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{table_name}" FORCE ROW LEVEL SECURITY'))
        predicate = (
            "id = NULLIF(current_setting('app.workspace_id', true), '')::uuid"
            if table_name == "workspaces"
            else "workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid"
        )
        op.execute(
            sa.text(
                f'CREATE POLICY "{table_name}_workspace_isolation" ON "{table_name}" '
                f"USING ({predicate}) WITH CHECK ({predicate})"
            )
        )


def downgrade() -> None:
    for table_name in reversed(TENANT_TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table_name}_workspace_isolation" ON "{table_name}"'))
        op.execute(sa.text(f'ALTER TABLE "{table_name}" NO FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{table_name}" DISABLE ROW LEVEL SECURITY'))

    op.drop_index("ix_audit_events_request_id", table_name="audit_events")
    op.drop_index("ix_audit_events_session_id", table_name="audit_events")
    op.drop_column("audit_events", "outcome")
    op.drop_column("audit_events", "request_id")
    op.drop_column("audit_events", "session_id")

    op.drop_table("user_sessions")
    op.drop_table("policies")
    op.drop_table("membership_roles")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("workspace_memberships")
    op.drop_table("teams")
    op.drop_table("users")
    op.drop_index("ix_workspaces_organization_id", table_name="workspaces")
    op.drop_constraint("fk_workspaces_organization_id", "workspaces", type_="foreignkey")
    op.drop_column("workspaces", "currency")
    op.drop_column("workspaces", "organization_id")
    op.drop_table("organizations")
