import runpy
from pathlib import Path
from uuid import UUID

import pytest

from grovello.access import OWNER_PERMISSIONS, access_directory
from grovello.business_imports import (
    BusinessImportConflictError,
    CreateImportJobCommand,
    SqlAlchemyBusinessImportStore,
)
from grovello.models import Base

WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000001")


def test_onboarding_and_import_tables_are_canonical_tenant_metadata() -> None:
    expected = {
        "workspace_onboardings",
        "import_jobs",
        "import_sources",
        "import_mapping_versions",
        "import_rows",
        "import_issues",
        "import_change_sets",
    }
    assert expected <= set(Base.metadata.tables)

    source = Base.metadata.tables["import_sources"]
    foreign_key_targets = {
        tuple(sorted(element.target_fullname for element in constraint.elements))
        for constraint in source.foreign_key_constraints
    }
    assert ("import_jobs.id", "import_jobs.workspace_id") in foreign_key_targets


def test_import_migration_enables_forced_rls_and_is_reversible() -> None:
    migration_path = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "0008_workspace_onboarding_import_foundation.py"
    )
    migration = runpy.run_path(str(migration_path))
    assert migration["down_revision"] == "0007"
    assert migration["TENANT_TABLES"] == (
        "workspace_onboardings",
        "import_jobs",
        "import_sources",
        "import_mapping_versions",
        "import_rows",
        "import_issues",
        "import_change_sets",
    )
    source = migration_path.read_text(encoding="utf-8")
    assert source.count("ENABLE ROW LEVEL SECURITY") == 1
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "current_setting('app.workspace_id'" in source
    assert "DROP POLICY IF EXISTS" in source


def test_import_permissions_follow_narrow_risk_tiers() -> None:
    migration_path = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "0008_workspace_onboarding_import_foundation.py"
    )
    permissions = {
        key: risk
        for key, _description, risk in runpy.run_path(str(migration_path))["IMPORT_PERMISSIONS"]
    }
    assert permissions == {
        "workspace.onboarding.read": "R0",
        "workspace.onboarding.write": "R1",
        "workspace.onboarding.activate": "R3",
        "business_truth.import.read": "R0",
        "business_truth.import.create": "R1",
        "business_truth.import.map": "R1",
        "business_truth.import.apply": "R2",
        "business_truth.import.cancel": "R1",
        "business_truth.import.compensate": "R4",
    }
    assert set(permissions) <= OWNER_PERMISSIONS
    analyst = access_directory._grants[("northstar-analyst", WORKSPACE_ID)]
    assert {"workspace.onboarding.read", "business_truth.import.read"} <= analyst.permissions
    assert "business_truth.import.create" not in analyst.permissions
    assert "business_truth.import.compensate" not in analyst.permissions


def _command(**overrides) -> CreateImportJobCommand:
    values = {
        "object_type": "product",
        "source_format": "csv",
        "schema_version": 1,
        "locale": "en",
        "original_filename": "products.csv",
        "content_type": "text/csv",
        "content_length": 128,
        "checksum_sha256": "a" * 64,
        "business_purpose": "Import the approved product catalog",
        "input_versions": {},
    }
    values.update(overrides)
    return CreateImportJobCommand(**values)


def test_import_source_contract_rejects_scope_and_format_confusion() -> None:
    store = SqlAlchemyBusinessImportStore(
        None, WORKSPACE_ID, None, max_source_bytes=1024, upload_ttl_seconds=1800
    )
    with pytest.raises(BusinessImportConflictError, match="not importable"):
        store._validate(_command(object_type="asset"))
    with pytest.raises(BusinessImportConflictError, match="do not match"):
        store._validate(_command(content_type="application/json"))
    with pytest.raises(BusinessImportConflictError, match="size limit"):
        store._validate(_command(content_length=1025))
