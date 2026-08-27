"""Create the canonical temporal football knowledge schema.

Revision ID: 0001_canonical_temporal_schema
Revises: None
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_canonical_temporal_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "canonical_entities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_canonical_entities"),
    )
    op.create_index(
        "ix_canonical_entities_entity_type",
        "canonical_entities",
        ["entity_type"],
    )

    op.create_table(
        "players",
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_name", sa.String(length=160), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("country_code", sa.String(length=3), nullable=True),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["canonical_entities.id"],
            name="fk_players_entity_id_canonical_entities",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("entity_id", name="pk_players"),
    )
    op.create_index("ix_players_canonical_name", "players", ["canonical_name"])

    op.create_table(
        "clubs",
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_name", sa.String(length=160), nullable=False),
        sa.Column("short_name", sa.String(length=80), nullable=True),
        sa.Column("country_code", sa.String(length=3), nullable=True),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["canonical_entities.id"],
            name="fk_clubs_entity_id_canonical_entities",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("entity_id", name="pk_clubs"),
    )
    op.create_index("ix_clubs_canonical_name", "clubs", ["canonical_name"])

    op.create_table(
        "coaches",
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_name", sa.String(length=160), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("country_code", sa.String(length=3), nullable=True),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["canonical_entities.id"],
            name="fk_coaches_entity_id_canonical_entities",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("entity_id", name="pk_coaches"),
    )
    op.create_index("ix_coaches_canonical_name", "coaches", ["canonical_name"])

    op.create_table(
        "competitions",
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_name", sa.String(length=160), nullable=False),
        sa.Column("country_code", sa.String(length=3), nullable=True),
        sa.Column("competition_type", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["canonical_entities.id"],
            name="fk_competitions_entity_id_canonical_entities",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("entity_id", name="pk_competitions"),
    )
    op.create_index(
        "ix_competitions_canonical_name",
        "competitions",
        ["canonical_name"],
    )

    op.create_table(
        "sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=True),
        sa.Column("reliability", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("licensing_notes", sa.Text(), nullable=True),
        sa.Column("terms_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "reliability >= 0 AND reliability <= 1",
            name="ck_sources_reliability_probability",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sources"),
        sa.UniqueConstraint("key", name="uq_sources_key"),
    )

    op.create_table(
        "model_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("git_sha", sa.String(length=64), nullable=True),
        sa.Column("config_hash", sa.String(length=128), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_model_versions"),
        sa.UniqueConstraint("key", name="uq_model_versions_key"),
    )

    op.create_table(
        "competition_seasons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("competition_id", sa.Uuid(), nullable=False),
        sa.Column("season_key", sa.String(length=32), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=True),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "ends_on IS NULL OR starts_on IS NULL OR ends_on > starts_on",
            name="ck_competition_seasons_season_date_window",
        ),
        sa.ForeignKeyConstraint(
            ["competition_id"],
            ["competitions.entity_id"],
            name="fk_competition_seasons_competition_id_competitions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_competition_seasons"),
        sa.UniqueConstraint(
            "competition_id",
            "season_key",
            name="uq_competition_seasons_competition_id",
        ),
    )
    op.create_index(
        "ix_competition_seasons_competition_id",
        "competition_seasons",
        ["competition_id"],
    )

    op.create_table(
        "source_entities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=256), nullable=False),
        sa.Column("canonical_entity_id", sa.Uuid(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("parser_version", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_source_entities_confidence_probability",
        ),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from",
            name="ck_source_entities_valid_time_window",
        ),
        sa.ForeignKeyConstraint(
            ["canonical_entity_id"],
            ["canonical_entities.id"],
            name="fk_source_entities_canonical_entity_id_canonical_entities",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            name="fk_source_entities_source_id_sources",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_source_entities"),
        sa.UniqueConstraint(
            "source_id",
            "entity_type",
            "external_id",
            "valid_from",
            name="uq_source_entities_temporal_identity",
        ),
    )
    op.create_index(
        "ix_source_entities_canonical",
        "source_entities",
        ["canonical_entity_id", "source_id"],
    )

    op.create_table(
        "football_events",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_football_events_confidence_probability",
        ),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from",
            name="ck_football_events_valid_time_window",
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["canonical_entities.id"],
            name="fk_football_events_entity_id_canonical_entities",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            name="fk_football_events_source_id_sources",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("event_id", name="pk_football_events"),
    )
    op.create_index(
        "ix_football_events_entity_valid",
        "football_events",
        ["entity_id", "valid_from"],
    )
    op.create_index(
        "ix_football_events_event_type",
        "football_events",
        ["event_type"],
    )
    op.create_index(
        "ix_football_events_observed",
        "football_events",
        ["observed_at"],
    )

    op.create_table(
        "matches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("competition_season_id", sa.Uuid(), nullable=False),
        sa.Column("home_club_id", sa.Uuid(), nullable=False),
        sa.Column("away_club_id", sa.Uuid(), nullable=False),
        sa.Column("kickoff_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("home_score", sa.Integer(), nullable=True),
        sa.Column("away_score", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "away_score IS NULL OR away_score >= 0",
            name="ck_matches_away_score_nonnegative",
        ),
        sa.CheckConstraint(
            "home_club_id <> away_club_id",
            name="ck_matches_different_clubs",
        ),
        sa.CheckConstraint(
            "home_score IS NULL OR home_score >= 0",
            name="ck_matches_home_score_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["away_club_id"],
            ["clubs.entity_id"],
            name="fk_matches_away_club_id_clubs",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["competition_season_id"],
            ["competition_seasons.id"],
            name="fk_matches_competition_season_id_competition_seasons",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["home_club_id"],
            ["clubs.entity_id"],
            name="fk_matches_home_club_id_clubs",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_matches"),
    )
    op.create_index(
        "ix_matches_season_kickoff",
        "matches",
        ["competition_season_id", "kickoff_at"],
    )

    op.create_table(
        "model_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("model_version_id", sa.Uuid(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["canonical_entities.id"],
            name="fk_model_snapshots_entity_id_canonical_entities",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["model_version_id"],
            ["model_versions.id"],
            name="fk_model_snapshots_model_version_id_model_versions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_model_snapshots"),
    )
    op.create_index(
        "ix_model_snapshots_entity_cutoff",
        "model_snapshots",
        ["entity_id", "data_cutoff"],
    )


def downgrade() -> None:
    op.drop_index("ix_model_snapshots_entity_cutoff", table_name="model_snapshots")
    op.drop_table("model_snapshots")

    op.drop_index("ix_matches_season_kickoff", table_name="matches")
    op.drop_table("matches")

    op.drop_index("ix_football_events_observed", table_name="football_events")
    op.drop_index("ix_football_events_event_type", table_name="football_events")
    op.drop_index("ix_football_events_entity_valid", table_name="football_events")
    op.drop_table("football_events")

    op.drop_index("ix_source_entities_canonical", table_name="source_entities")
    op.drop_table("source_entities")

    op.drop_index(
        "ix_competition_seasons_competition_id",
        table_name="competition_seasons",
    )
    op.drop_table("competition_seasons")
    op.drop_table("model_versions")
    op.drop_table("sources")

    op.drop_index("ix_competitions_canonical_name", table_name="competitions")
    op.drop_table("competitions")
    op.drop_index("ix_coaches_canonical_name", table_name="coaches")
    op.drop_table("coaches")
    op.drop_index("ix_clubs_canonical_name", table_name="clubs")
    op.drop_table("clubs")
    op.drop_index("ix_players_canonical_name", table_name="players")
    op.drop_table("players")

    op.drop_index(
        "ix_canonical_entities_entity_type",
        table_name="canonical_entities",
    )
    op.drop_table("canonical_entities")
