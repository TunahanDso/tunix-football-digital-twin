from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
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


class SquadMembershipRecord(CreatedAtMixin, Base):
    """Stable identity for one player's spell at one club."""

    __tablename__ = "player_squad_memberships"
    __table_args__ = (
        UniqueConstraint(
            "player_id",
            "club_id",
            "spell_key",
            name="uq_squad_memberships_player_club_spell",
        ),
        Index("ix_squad_memberships_club_player", "club_id", "player_id"),
        Index("ix_squad_memberships_player", "player_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    player_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "players.entity_id",
            name="fk_squad_memberships_player_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    club_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "clubs.entity_id",
            name="fk_squad_memberships_club_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    spell_key: Mapped[str] = mapped_column(String(160), nullable=False)


class SquadMembershipRevisionRecord(CreatedAtMixin, Base):
    """Append-only bitemporal interpretation of a squad-membership spell."""

    __tablename__ = "player_squad_membership_revisions"
    __table_args__ = (
        UniqueConstraint(
            "membership_id",
            "revision_number",
            name="uq_squad_membership_revisions_membership_revision",
        ),
        CheckConstraint("revision_number > 0", name="positive_revision"),
        CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from",
            name="valid_time_window",
        ),
        CheckConstraint(
            "shirt_number IS NULL OR shirt_number > 0",
            name="positive_shirt_number",
        ),
        Index(
            "ix_squad_membership_revisions_membership_observed",
            "membership_id",
            "observed_at",
        ),
        Index(
            "ix_squad_membership_revisions_validity",
            "valid_from",
            "valid_until",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    membership_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "player_squad_memberships.id",
            name="fk_squad_membership_revisions_membership_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    membership_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    shirt_number: Mapped[int | None] = mapped_column(Integer)
    source_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "sources.id",
            name="fk_squad_membership_revisions_source_id",
            ondelete="SET NULL",
        ),
    )
    raw_record_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "raw_source_records.record_id",
            name="fk_squad_membership_revisions_raw_record_id",
            ondelete="SET NULL",
        ),
    )
    reason: Mapped[str | None] = mapped_column(Text)
