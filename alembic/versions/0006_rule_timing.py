"""Separate rule observation time from effective time.

Revision ID: 0006_rule_timing
Revises: 0005_comp_history
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006_rule_timing"
down_revision: str | None = "0005_comp_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_season_rule_versions_valid_before_observed",
        "season_rule_versions",
        type_="check",
    )


def downgrade() -> None:
    op.create_check_constraint(
        "ck_season_rule_versions_valid_before_observed",
        "season_rule_versions",
        "valid_from <= observed_at",
    )
