import runpy
from pathlib import Path

from sqlalchemy.dialects.postgresql import UUID

from grovello.models import Base


def test_import_apply_metadata_has_tenant_lineage_and_concurrency_guards() -> None:
    jobs = Base.metadata.tables["import_jobs"]
    change_sets = Base.metadata.tables["import_change_sets"]
    operations = Base.metadata.tables["import_change_set_operations"]
    onboarding = Base.metadata.tables["workspace_onboardings"]

    assert isinstance(jobs.c.selected_change_set_id.type, UUID)
    assert jobs.c.apply_workflow_id.unique is True
    assert jobs.c.compensation_workflow_id.unique is True
    assert onboarding.c.activation_snapshot.nullable is False
    assert change_sets.c.business_purpose.nullable is False
    assert {
        tuple(column.name for column in constraint.columns)
        for constraint in operations.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    } >= {
        ("workspace_id", "change_set_id", "sequence"),
        ("workspace_id", "operation_key"),
    }


def test_import_apply_migration_is_reversible_and_forces_rls() -> None:
    migration_path = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "0011_import_apply_activation.py"
    )
    migration = runpy.run_path(str(migration_path))
    source = migration_path.read_text(encoding="utf-8")
    assert migration["down_revision"] == "0010"
    assert "import_change_set_operations_workspace_isolation" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "activation_snapshot" in source
    assert "drop_table(\"import_change_set_operations\")" in source


def test_apply_and_compensation_use_versioned_business_truth_without_history_rewrite() -> None:
    activity_path = (
        Path(__file__).parents[1] / "src" / "grovello" / "import_apply_activity.py"
    )
    source = activity_path.read_text(encoding="utf-8")
    assert "SqlAlchemyBusinessTruthStore" in source
    assert "expected_version_id" in source
    assert "source_type=\"import\"" in source
    assert "CreateBusinessObjectVersionCommand" in source
    assert "delete(BusinessObject" not in source
    assert "BusinessImportCompensationBlocked" in source
