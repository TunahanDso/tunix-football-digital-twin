"""Add versioned competition rules, participation and match revisions.

Revision ID: 0005_comp_history
Revises: 0004_baseline_backtest_harness
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_comp_history"
down_revision: str | None = "0004_baseline_backtest_harness"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "season_rule_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("competition_season_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_season_rule_versions_positive_version"),
        sa.CheckConstraint(
            "valid_from <= observed_at",
            name="ck_season_rule_versions_valid_before_observed",
        ),
        sa.ForeignKeyConstraint(
            ["competition_season_id"],
            ["competition_seasons.id"],
            name="fk_season_rule_versions_season",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"],
            ["season_rule_versions.id"],
            name="fk_season_rule_versions_supersedes",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_season_rule_versions"),
        sa.UniqueConstraint(
            "competition_season_id",
            "version",
            name="uq_season_rule_versions_season_version",
        ),
    )
    op.create_index(
        "ix_season_rule_versions_season_valid",
        "season_rule_versions",
        ["competition_season_id", "valid_from"],
    )

    op.create_table(
        "season_club_participations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("competition_season_id", sa.Uuid(), nullable=False),
        sa.Column("club_id", sa.Uuid(), nullable=False),
        sa.Column("entry_type", sa.String(length=32), nullable=False),
        sa.Column("exit_type", sa.String(length=32), nullable=False),
        sa.Column("from_competition_id", sa.Uuid(), nullable=True),
        sa.Column("to_competition_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.entity_id"],
            name="fk_season_participations_club",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["competition_season_id"],
            ["competition_seasons.id"],
            name="fk_season_participations_season",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["from_competition_id"],
            ["competitions.entity_id"],
            name="fk_season_participations_from_comp",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["to_competition_id"],
            ["competitions.entity_id"],
            name="fk_season_participations_to_comp",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_season_club_participations"),
        sa.UniqueConstraint(
            "competition_season_id",
            "club_id",
            name="uq_season_participations_season_club",
        ),
    )
    op.create_index(
        "ix_season_participations_club",
        "season_club_participations",
        ["club_id", "competition_season_id"],
    )

    op.create_table(
        "match_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("revision_kind", sa.String(length=32), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kickoff_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("home_score", sa.Integer(), nullable=True),
        sa.Column("away_score", sa.Integer(), nullable=True),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("raw_record_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "revision_number > 0",
            name="ck_match_revisions_positive_revision",
        ),
        sa.CheckConstraint(
            "home_score IS NULL OR home_score >= 0",
            name="ck_match_revisions_home_score_nonnegative",
        ),
        sa.CheckConstraint(
            "away_score IS NULL OR away_score >= 0",
            name="ck_match_revisions_away_score_nonnegative",
        ),
        sa.CheckConstraint(
            "status NOT IN ('finished', 'awarded') "
            "OR (home_score IS NOT NULL AND away_score IS NOT NULL)",
            name="ck_match_revisions_completed_requires_score",
        ),
        sa.CheckConstraint(
            "status NOT IN ('scheduled', 'postponed', 'cancelled') "
            "OR (home_score IS NULL AND away_score IS NULL)",
            name="ck_match_revisions_unplayed_has_no_score",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            name="fk_match_revisions_match",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["raw_record_id"],
            ["raw_source_records.record_id"],
            name="fk_match_revisions_raw_record",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            name="fk_match_revisions_source",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_match_revisions"),
        sa.UniqueConstraint(
            "match_id",
            "revision_number",
            name="uq_match_revisions_match_revision",
        ),
    )
    op.create_index(
        "ix_match_revisions_match_observed",
        "match_revisions",
        ["match_id", "observed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_match_revisions_match_observed", table_name="match_revisions")
    op.drop_table("match_revisions")
    op.drop_index("ix_season_participations_club", table_name="season_club_participations")
    op.drop_table("season_club_participations")
    op.drop_index("ix_season_rule_versions_season_valid", table_name="season_rule_versions")
    op.drop_table("season_rule_versions")
