"""Add reproducible baseline backtest runs and aligned predictions.

Revision ID: 0004_baseline_backtest_harness
Revises: 0003_entity_resolution_core
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_baseline_backtest_harness"
down_revision: str | None = "0003_entity_resolution_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backtest_runs",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("model_version_id", sa.Uuid(), nullable=False),
        sa.Column("model_key", sa.String(length=80), nullable=False),
        sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column("data_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("lead_time_seconds", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("max_data_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "lead_time_seconds > 0",
            name="ck_backtest_runs_positive_lead_time",
        ),
        sa.CheckConstraint(
            "seed >= 0",
            name="ck_backtest_runs_nonnegative_seed",
        ),
        sa.ForeignKeyConstraint(
            ["model_version_id"],
            ["model_versions.id"],
            name="fk_backtest_runs_model_version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("run_id", name="pk_backtest_runs"),
    )
    op.create_index(
        "ix_backtest_runs_model_started",
        "backtest_runs",
        ["model_key", "started_at"],
    )

    op.create_table(
        "backtest_predictions",
        sa.Column("prediction_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=False),
        sa.Column("prediction_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("train_match_count", sa.Integer(), nullable=False),
        sa.Column("home_win_probability", sa.Numeric(precision=10, scale=8), nullable=False),
        sa.Column("draw_probability", sa.Numeric(precision=10, scale=8), nullable=False),
        sa.Column("away_win_probability", sa.Numeric(precision=10, scale=8), nullable=False),
        sa.Column("expected_home_goals", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column("expected_away_goals", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column("actual_home_goals", sa.Integer(), nullable=False),
        sa.Column("actual_away_goals", sa.Integer(), nullable=False),
        sa.Column("market_snapshot_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("market_home_probability", sa.Numeric(precision=10, scale=8), nullable=True),
        sa.Column("market_draw_probability", sa.Numeric(precision=10, scale=8), nullable=True),
        sa.Column("market_away_probability", sa.Numeric(precision=10, scale=8), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "data_cutoff <= prediction_cutoff",
            name="ck_backtest_predictions_data_before_prediction",
        ),
        sa.CheckConstraint(
            "market_snapshot_at IS NULL OR market_snapshot_at <= prediction_cutoff",
            name="ck_backtest_predictions_market_before_prediction",
        ),
        sa.CheckConstraint(
            "home_win_probability >= 0 AND home_win_probability <= 1",
            name="ck_backtest_predictions_home_probability_range",
        ),
        sa.CheckConstraint(
            "draw_probability >= 0 AND draw_probability <= 1",
            name="ck_backtest_predictions_draw_probability_range",
        ),
        sa.CheckConstraint(
            "away_win_probability >= 0 AND away_win_probability <= 1",
            name="ck_backtest_predictions_away_probability_range",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            name="fk_backtest_predictions_match",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["backtest_runs.run_id"],
            name="fk_backtest_predictions_run",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("prediction_id", name="pk_backtest_predictions"),
        sa.UniqueConstraint(
            "run_id",
            "match_id",
            name="uq_backtest_predictions_run_match",
        ),
    )
    op.create_index(
        "ix_backtest_predictions_cutoff",
        "backtest_predictions",
        ["prediction_cutoff"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_backtest_predictions_cutoff",
        table_name="backtest_predictions",
    )
    op.drop_table("backtest_predictions")
    op.drop_index("ix_backtest_runs_model_started", table_name="backtest_runs")
    op.drop_table("backtest_runs")
