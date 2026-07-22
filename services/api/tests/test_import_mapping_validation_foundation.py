import runpy
from pathlib import Path

from sqlalchemy.dialects.postgresql import UUID

from grovello.models import Base


def test_mapping_validation_metadata_preserves_workspace_lineage() -> None:
    jobs = Base.metadata.tables["import_jobs"]
    mappings = Base.metadata.tables["import_mapping_versions"]
    assert isinstance(jobs.c.selected_mapping_version_id.type, UUID)
    assert jobs.c.validation_workflow_id.unique is True
    assert jobs.c.validation_business_purpose.type.length == 240
    assert mappings.c.source_fields.nullable is False
    assert mappings.c.business_purpose.type.length == 240
    assert {
        tuple(column.name for column in constraint.columns)
        for constraint in mappings.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    } >= {
        ("workspace_id", "job_id", "version"),
        ("workspace_id", "job_id", "idempotency_key"),
    }


def test_mapping_validation_migration_is_reversible_and_does_not_apply_business_truth() -> None:
    migration_path = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "0010_import_mapping_validation.py"
    )
    migration = runpy.run_path(str(migration_path))
    assert migration["down_revision"] == "0009"
    source = migration_path.read_text(encoding="utf-8")
    assert "selected_mapping_version_id" in source
    assert "validation_workflow_id" in source
    assert "import_rows" not in source
    assert "business_objects" not in source
    assert "drop_table" not in source
