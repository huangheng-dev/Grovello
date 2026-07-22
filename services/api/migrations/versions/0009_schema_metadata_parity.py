"""Align foundational query indexes with canonical ORM metadata.

Revision ID: 0009
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FOUNDATION_INDEXES = (
    ("ix_runs_workflow_type", "runs", ("workflow_type",)),
    ("ix_audit_events_action", "audit_events", ("action",)),
    ("ix_outbox_events_aggregate_id", "outbox_events", ("aggregate_id",)),
)


def upgrade() -> None:
    for name, table_name, columns in FOUNDATION_INDEXES:
        op.create_index(name, table_name, list(columns))


def downgrade() -> None:
    for name, table_name, _columns in reversed(FOUNDATION_INDEXES):
        op.drop_index(name, table_name=table_name)
