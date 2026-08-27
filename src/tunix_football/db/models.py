from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from tunix_football.db.base import Base, CreatedAtMixin


class CanonicalEntity(CreatedAtMixin, Base):
    """Stable TUNIX identity shared by every source-independent football entity."""

    __tablename__ = "canonical_entities"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Player(Base):
    __tablename__ = "players"

    entity_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("canonical_entities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    canonical_name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    birth_date: Mapped[date | None] = mapped_column(Date)
    country_code: Mapped[str | None] = mapped_column(String(3))


class Club(Base):
    __tablename__ = "clubs"

    entity_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("canonical_entities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    canonical_name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    short_name: Mapped[str | None] = mapped_column(String(80))
    country_code: Mapped[str | None] = mapped_column(String(3))


class Coach(Base):
    __tablename__ = "coaches"

    entity_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("canonical_entities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    canonical_name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    birth_date: Mapped[date | None] = mapped_column(Date)
    country_code: Mapped[str | None] = mapped_column(String(3))


class Competition(Base):
    __tablename__ = "competitions"

    entity_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("canonical_entities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    canonical_name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    country_code: Mapped[str | None] = mapped_column(String(3))
    competition_type: Mapped[str] = mapped_column(String(32), nullable=False)


class CompetitionSeason(CreatedAtMixin, Base):
    __tablename__ = "competition_seasons"
    __table_args__ = (
        UniqueConstraint("competition_id", "season_key"),
        CheckConstraint(
            "ends_on IS NULL OR starts_on IS NULL OR ends_on > starts_on",
            name="season_date_window",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    competition_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("competitions.entity_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    season_key: Mapped[str] = mapped_column(String(32), nullable=False)
    starts_on: Mapped[date | None] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)
    rules: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Match(CreatedAtMixin, Base):
    __tablename__ = "matches"
    __table_args__ = (
        CheckConstraint(
            "home_score IS NULL OR home_score >= 0",
            name="home_score_nonnegative",
        ),
        CheckConstraint(
            "away_score IS NULL OR away_score >= 0",
            name="away_score_nonnegative",
        ),
        CheckConstraint("home_club_id <> away_club_id", name="different_clubs"),
        Index("ix_matches_season_kickoff", "competition_season_id", "kickoff_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    competition_season_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("competition_seasons.id", ondelete="CASCADE"),
        nullable=False,
    )
    home_club_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("clubs.entity_id", ondelete="RESTRICT"),
        nullable=False,
    )
    away_club_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("clubs.entity_id", ondelete="RESTRICT"),
        nullable=False,
    )
    kickoff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="scheduled")
    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)


class Source(CreatedAtMixin, Base):
    __tablename__ = "sources"
    __table_args__ = (
        CheckConstraint(
            "reliability >= 0 AND reliability <= 1",
            name="reliability_probability",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(512))
    reliability: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
        default=Decimal("0.5000"),
    )
    licensing_notes: Mapped[str | None] = mapped_column(Text)
    terms_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SourceEntity(CreatedAtMixin, Base):
    """Maps provider-local identity to a stable TUNIX canonical entity."""

    __tablename__ = "source_entities"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "entity_type",
            "external_id",
            "valid_from",
            name="uq_source_entities_temporal_identity",
        ),
        CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from",
            name="valid_time_window",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="confidence_probability",
        ),
        Index("ix_source_entities_canonical", "canonical_entity_id", "source_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(256), nullable=False)
    canonical_entity_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("canonical_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(64), nullable=False)


class FootballEventRecord(CreatedAtMixin, Base):
    __tablename__ = "football_events"
    __table_args__ = (
        CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from",
            name="valid_time_window",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="confidence_probability",
        ),
        Index("ix_football_events_entity_valid", "entity_id", "valid_from"),
        Index("ix_football_events_observed", "observed_at"),
    )

    event_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("canonical_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class ModelVersion(CreatedAtMixin, Base):
    __tablename__ = "model_versions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    git_sha: Mapped[str | None] = mapped_column(String(64))
    config_hash: Mapped[str | None] = mapped_column(String(128))
    notes: Mapped[str | None] = mapped_column(Text)


class ModelSnapshot(CreatedAtMixin, Base):
    __tablename__ = "model_snapshots"
    __table_args__ = (
        Index("ix_model_snapshots_entity_cutoff", "entity_id", "data_cutoff"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    model_version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("model_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    entity_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("canonical_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
