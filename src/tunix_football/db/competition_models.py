from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from tunix_football.db.base import Base, CreatedAtMixin


class SeasonRuleVersionRecord(CreatedAtMixin, Base):
    __tablename__ = "season_rule_versions"
    __table_args__ = (
        UniqueConstraint(
            "competition_season_id",
            "version",
            name="uq_season_rule_versions_season_version",
        ),
        CheckConstraint("version > 0", name="positive_version"),
        Index(
            "ix_season_rule_versions_season_valid",
            "competition_season_id",
            "valid_from",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    competition_season_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("competition_seasons.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    supersedes_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("season_rule_versions.id", ondelete="RESTRICT"),
    )
    rules: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class SeasonClubParticipationRecord(CreatedAtMixin, Base):
    __tablename__ = "season_club_participations"
    __table_args__ = (
        UniqueConstraint(
            "competition_season_id",
            "club_id",
            name="uq_season_club_participations_season_club",
        ),
        Index(
            "ix_season_club_participations_club",
            "club_id",
            "competition_season_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    competition_season_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("competition_seasons.id", ondelete="CASCADE"),
        nullable=False,
    )
    club_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("clubs.entity_id", ondelete="RESTRICT"),
        nullable=False,
    )
    entry_type: Mapped[str] = mapped_column(String(32), nullable=False)
    exit_type: Mapped[str] = mapped_column(String(32), nullable=False)
    from_competition_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("competitions.entity_id", ondelete="SET NULL"),
    )
    to_competition_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("competitions.entity_id", ondelete="SET NULL"),
    )


class MatchRevisionRecord(CreatedAtMixin, Base):
    __tablename__ = "match_revisions"
    __table_args__ = (
        UniqueConstraint(
            "match_id",
            "revision_number",
            name="uq_match_revisions_match_revision",
        ),
        CheckConstraint("revision_number > 0", name="positive_revision"),
        CheckConstraint(
            "home_score IS NULL OR home_score >= 0",
            name="home_score_nonnegative",
        ),
        CheckConstraint(
            "away_score IS NULL OR away_score >= 0",
            name="away_score_nonnegative",
        ),
        CheckConstraint(
            "status NOT IN ('finished', 'awarded') "
            "OR (home_score IS NOT NULL AND away_score IS NOT NULL)",
            name="completed_requires_score",
        ),
        CheckConstraint(
            "status NOT IN ('scheduled', 'postponed', 'cancelled') "
            "OR (home_score IS NULL AND away_score IS NULL)",
            name="unplayed_has_no_score",
        ),
        Index("ix_match_revisions_match_observed", "match_id", "observed_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    match_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("matches.id", ondelete="CASCADE"),
        nullable=False,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    kickoff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)
    source_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("sources.id", ondelete="SET NULL"),
    )
    raw_record_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("raw_source_records.record_id", ondelete="SET NULL"),
    )
    reason: Mapped[str | None] = mapped_column(Text)
