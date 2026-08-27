"""Add stable per-source identities for collector runs and raw evidence.

Revision ID: 0007_evidence_identity
Revises: 0006_rule_timing
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_evidence_identity"
down_revision: str | None = "0006_rule_timing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "collector_runs",
        sa.Column("run_key", sa.String(length=160), nullable=True),
    )
    op.create_unique_constraint(
        "uq_collector_runs_source_run_key",
        "collector_runs",
        ["source_id", "run_key"],
    )
    op.add_column(
        "raw_source_records",
        sa.Column("evidence_key", sa.String(length=256), nullable=True),
    )
    op.create_unique_constraint(
        "uq_raw_source_records_source_evidence_key",
        "raw_source_records",
        ["source_id", "evidence_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_raw_source_records_source_evidence_key",
        "raw_source_records",
        type_="unique",
    )
    op.drop_column("raw_source_records", "evidence_key")
    op.drop_constraint(
        "uq_collector_runs_source_run_key",
        "collector_runs",
        type_="unique",
    )
    op.drop_column("collector_runs", "run_key")
