import asyncio
import uuid

from sqlalchemy import text

from grovello.access import (
    NORTHSTAR_ORGANIZATION_ID,
    NORTHSTAR_WORKSPACE_ID,
    OWNER_PERMISSIONS,
)
from grovello.config import get_settings
from grovello.database import session_factory

NORTHSTAR_USER_ID = uuid.UUID("00000000-0000-4000-8000-000000002001")
NORTHSTAR_TEAM_ID = uuid.UUID("00000000-0000-4000-8000-000000003001")
NORTHSTAR_MEMBERSHIP_ID = uuid.UUID("00000000-0000-4000-8000-000000004001")
NORTHSTAR_OWNER_ROLE_ID = uuid.UUID("00000000-0000-4000-8000-000000005001")
NORTHSTAR_POLICY_ID = uuid.UUID("00000000-0000-4000-8000-000000006001")


async def seed_development_access() -> None:
    settings = get_settings()
    if settings.environment == "production":
        raise RuntimeError("Development seed is disabled in production")

    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                """
                INSERT INTO organizations (id, slug, name, status)
                VALUES (:id, 'northstar-industrial', 'Northstar Industrial', 'active')
                ON CONFLICT (id) DO UPDATE SET
                    slug = EXCLUDED.slug,
                    name = EXCLUDED.name,
                    status = EXCLUDED.status
                """
            ),
            {"id": NORTHSTAR_ORGANIZATION_ID},
        )
        await session.execute(
            text("SELECT set_config('app.workspace_id', :workspace_id, true)"),
            {"workspace_id": str(NORTHSTAR_WORKSPACE_ID)},
        )
        await session.execute(
            text(
                """
                INSERT INTO workspaces
                    (id, organization_id, slug, name, default_locale, timezone, currency)
                VALUES
                    (:id, :organization_id, 'northstar-industrial', 'Northstar Industrial',
                     'en', 'Asia/Shanghai', 'USD')
                ON CONFLICT (id) DO UPDATE SET
                    organization_id = EXCLUDED.organization_id,
                    slug = EXCLUDED.slug,
                    name = EXCLUDED.name,
                    default_locale = EXCLUDED.default_locale,
                    timezone = EXCLUDED.timezone,
                    currency = EXCLUDED.currency
                """
            ),
            {"id": NORTHSTAR_WORKSPACE_ID, "organization_id": NORTHSTAR_ORGANIZATION_ID},
        )
        await session.execute(
            text(
                """
                INSERT INTO users
                    (id, organization_id, external_subject, email, display_name, status)
                VALUES
                    (:id, :organization_id, 'northstar-owner',
                     'owner@northstar.example.invalid', 'Northstar Owner', 'active')
                ON CONFLICT (id) DO UPDATE SET
                    external_subject = EXCLUDED.external_subject,
                    email = EXCLUDED.email,
                    display_name = EXCLUDED.display_name,
                    status = EXCLUDED.status
                """
            ),
            {"id": NORTHSTAR_USER_ID, "organization_id": NORTHSTAR_ORGANIZATION_ID},
        )
        await session.execute(
            text(
                """
                INSERT INTO teams (id, workspace_id, slug, name)
                VALUES (:id, :workspace_id, 'growth-operations', 'Growth Operations')
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
                """
            ),
            {"id": NORTHSTAR_TEAM_ID, "workspace_id": NORTHSTAR_WORKSPACE_ID},
        )
        await session.execute(
            text(
                """
                INSERT INTO workspace_memberships (id, workspace_id, user_id, status)
                VALUES (:id, :workspace_id, :user_id, 'active')
                ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status
                """
            ),
            {
                "id": NORTHSTAR_MEMBERSHIP_ID,
                "workspace_id": NORTHSTAR_WORKSPACE_ID,
                "user_id": NORTHSTAR_USER_ID,
            },
        )
        await session.execute(
            text(
                """
                INSERT INTO roles (id, workspace_id, key, name, description, is_system)
                VALUES
                    (:id, :workspace_id, 'workspace_owner', 'Workspace Owner',
                     'Full control of the fictional development workspace', true)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    is_system = EXCLUDED.is_system
                """
            ),
            {"id": NORTHSTAR_OWNER_ROLE_ID, "workspace_id": NORTHSTAR_WORKSPACE_ID},
        )
        for permission in sorted(OWNER_PERMISSIONS):
            await session.execute(
                text(
                    """
                    INSERT INTO permissions (key, description, risk_tier)
                    VALUES (:key, :description, 'R1')
                    ON CONFLICT (key) DO UPDATE SET description = EXCLUDED.description
                    """
                ),
                {"key": permission, "description": f"Development permission: {permission}"},
            )
            await session.execute(
                text(
                    """
                    INSERT INTO role_permissions (workspace_id, role_id, permission_key)
                    VALUES (:workspace_id, :role_id, :permission_key)
                    ON CONFLICT DO NOTHING
                    """
                ),
                {
                    "workspace_id": NORTHSTAR_WORKSPACE_ID,
                    "role_id": NORTHSTAR_OWNER_ROLE_ID,
                    "permission_key": permission,
                },
            )
        await session.execute(
            text(
                """
                INSERT INTO membership_roles (workspace_id, membership_id, role_id)
                VALUES (:workspace_id, :membership_id, :role_id)
                ON CONFLICT DO NOTHING
                """
            ),
            {
                "workspace_id": NORTHSTAR_WORKSPACE_ID,
                "membership_id": NORTHSTAR_MEMBERSHIP_ID,
                "role_id": NORTHSTAR_OWNER_ROLE_ID,
            },
        )
        await session.execute(
            text(
                """
                INSERT INTO policies (id, workspace_id, key, version, status, rules)
                VALUES (:id, :workspace_id, 'development-baseline', 1, 'active', CAST(:rules AS json))
                ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status, rules = EXCLUDED.rules
                """
            ),
            {
                "id": NORTHSTAR_POLICY_ID,
                "workspace_id": NORTHSTAR_WORKSPACE_ID,
                "rules": '{"fixture":"fictional","externalActions":"approval_required"}',
            },
        )


async def main() -> None:
    await seed_development_access()
    print(f"Seeded fictional development workspace {NORTHSTAR_WORKSPACE_ID}")


if __name__ == "__main__":
    asyncio.run(main())
