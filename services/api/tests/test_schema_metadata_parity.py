import runpy
from pathlib import Path

from sqlalchemy.dialects.postgresql import JSONB

from grovello.models import Base


def test_historical_unique_constraints_and_lookup_indexes_are_both_declared() -> None:
    expected = {
        "organizations": ("slug", "ix_organizations_slug"),
        "workspaces": ("slug", "ix_workspaces_slug"),
        "users": ("external_subject", "ix_users_external_subject"),
    }
    for table_name, (column_name, index_name) in expected.items():
        table = Base.metadata.tables[table_name]
        unique_columns = {
            tuple(column.name for column in constraint.columns)
            for constraint in table.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        }
        assert (column_name,) in unique_columns
        assert index_name in {index.name for index in table.indexes}
        index = next(index for index in table.indexes if index.name == index_name)
        assert index.unique is False


def test_asset_finalization_payload_matches_existing_jsonb_storage() -> None:
    column = Base.metadata.tables["asset_upload_sessions"].c.finalization_payload
    assert isinstance(column.type, JSONB)


def test_schema_parity_migration_is_narrow_and_reversible() -> None:
    migration_path = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "0009_schema_metadata_parity.py"
    )
    migration = runpy.run_path(str(migration_path))
    assert migration["down_revision"] == "0008"
    assert migration["FOUNDATION_INDEXES"] == (
        ("ix_runs_workflow_type", "runs", ("workflow_type",)),
        ("ix_audit_events_action", "audit_events", ("action",)),
        ("ix_outbox_events_aggregate_id", "outbox_events", ("aggregate_id",)),
    )
    source = migration_path.read_text(encoding="utf-8")
    assert "create_index" in source
    assert "drop_index" in source
    assert "drop_column" not in source
    assert "alter_column" not in source
