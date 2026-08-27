from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from tunix_football.canonical_ids import canonical_id
from tunix_football.db.models import Player
from tunix_football.db.squad_models import (
    SquadMembershipRecord,
    SquadMembershipRevisionRecord,
)


@dataclass(frozen=True, slots=True)
class SquadMemberSnapshot:
    membership_id: UUID
    spell_key: str
    player_id: UUID
    player_name: str
    club_id: UUID
    revision_number: int
    observed_at: datetime
    valid_from: datetime
    valid_until: datetime | None
    membership_kind: str
    shirt_number: int | None


class SquadQuery:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def squad_at(
        self,
        club_key: str,
        *,
        as_of: datetime,
        knowledge_cutoff: datetime,
    ) -> list[SquadMemberSnapshot]:
        self._require_aware(as_of, "as_of")
        self._require_aware(knowledge_cutoff, "knowledge_cutoff")
        club_id = canonical_id("club", club_key)

        latest_known = (
            select(
                SquadMembershipRevisionRecord.membership_id.label("membership_id"),
                func.max(SquadMembershipRevisionRecord.revision_number).label(
                    "revision_number"
                ),
            )
            .where(SquadMembershipRevisionRecord.observed_at <= knowledge_cutoff)
            .group_by(SquadMembershipRevisionRecord.membership_id)
            .subquery()
        )

        statement = (
            select(
                SquadMembershipRecord,
                SquadMembershipRevisionRecord,
                Player,
            )
            .join(
                latest_known,
                latest_known.c.membership_id == SquadMembershipRecord.id,
            )
            .join(
                SquadMembershipRevisionRecord,
                and_(
                    SquadMembershipRevisionRecord.membership_id
                    == latest_known.c.membership_id,
                    SquadMembershipRevisionRecord.revision_number
                    == latest_known.c.revision_number,
                ),
            )
            .join(Player, Player.entity_id == SquadMembershipRecord.player_id)
            .where(SquadMembershipRecord.club_id == club_id)
            .where(SquadMembershipRevisionRecord.valid_from <= as_of)
            .where(
                or_(
                    SquadMembershipRevisionRecord.valid_until.is_(None),
                    SquadMembershipRevisionRecord.valid_until > as_of,
                )
            )
            .order_by(Player.canonical_name, SquadMembershipRecord.spell_key)
        )

        result = await self._session.execute(statement)
        return [
            SquadMemberSnapshot(
                membership_id=membership.id,
                spell_key=membership.spell_key,
                player_id=player.entity_id,
                player_name=player.canonical_name,
                club_id=membership.club_id,
                revision_number=revision.revision_number,
                observed_at=revision.observed_at,
                valid_from=revision.valid_from,
                valid_until=revision.valid_until,
                membership_kind=revision.membership_kind,
                shirt_number=revision.shirt_number,
            )
            for membership, revision, player in result.all()
        ]

    @staticmethod
    def _require_aware(value: datetime, label: str) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{label} must be timezone-aware")
