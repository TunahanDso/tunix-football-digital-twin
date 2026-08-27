from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from tunix_football.canonical_ids import canonical_id
from tunix_football.db.models import CanonicalEntity, Club, Player
from tunix_football.db.squad_models import (
    SquadMembershipRecord,
    SquadMembershipRevisionRecord,
)
from tunix_football.squad.contracts import (
    PlayerSeed,
    SquadHistorySeed,
    SquadMembershipObservation,
)


@dataclass(slots=True)
class SquadImportSummary:
    inserted: int = 0
    existing: int = 0
    conflicting: int = 0

    def mark(self, *, existed: bool) -> None:
        if existed:
            self.existing += 1
        else:
            self.inserted += 1

    def mark_conflict(self) -> None:
        self.conflicting += 1


class SquadImportConflict(ValueError):
    """Raised when a stable squad-history logical key conflicts with stored truth."""

    def __init__(self, message: str, *, summary: SquadImportSummary) -> None:
        super().__init__(message)
        self.summary = summary


class SquadHistoryWriter:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def import_dataset(self, seed: SquadHistorySeed) -> SquadImportSummary:
        summary = SquadImportSummary()
        async with self._session.begin():
            for player in seed.players:
                await self._persist_player(player, summary)
            await self._session.flush()

            first_by_spell: dict[str, SquadMembershipObservation] = {}
            for observation in seed.observations:
                first_by_spell.setdefault(observation.spell_key, observation)

            memberships: dict[str, UUID] = {}
            for spell_key, observation in first_by_spell.items():
                membership_id = await self._persist_membership(observation, summary)
                memberships[spell_key] = membership_id
            await self._session.flush()

            for observation in seed.observations:
                await self._persist_revision(
                    memberships[observation.spell_key],
                    observation,
                    summary,
                )
        return summary

    async def _persist_player(
        self,
        player: PlayerSeed,
        summary: SquadImportSummary,
    ) -> None:
        player_id = canonical_id("player", player.key)
        await self._persist_entity(player_id, "player", summary)
        existing = await self._session.get(Player, player_id)
        expected = {
            "canonical_name": player.name,
            "birth_date": player.birth_date,
            "country_code": player.country_code,
        }
        if existing is None:
            self._session.add(
                Player(
                    entity_id=player_id,
                    canonical_name=player.name,
                    birth_date=player.birth_date,
                    country_code=player.country_code,
                )
            )
            summary.mark(existed=False)
            return
        self._assert_fields(f"player:{player.key}", existing, expected, summary)
        summary.mark(existed=True)

    async def _persist_entity(
        self,
        entity_id: UUID,
        entity_type: str,
        summary: SquadImportSummary,
    ) -> None:
        existing = await self._session.get(CanonicalEntity, entity_id)
        if existing is None:
            self._session.add(
                CanonicalEntity(
                    id=entity_id,
                    entity_type=entity_type,
                    retired_at=None,
                )
            )
            summary.mark(existed=False)
            return
        self._assert_fields(
            f"canonical_entity:{entity_id}",
            existing,
            {"entity_type": entity_type, "retired_at": None},
            summary,
        )
        summary.mark(existed=True)

    async def _persist_membership(
        self,
        observation: SquadMembershipObservation,
        summary: SquadImportSummary,
    ) -> UUID:
        player_id = canonical_id("player", observation.player_key)
        club_id = canonical_id("club", observation.club_key)
        club = await self._session.get(Club, club_id)
        if club is None:
            summary.mark_conflict()
            raise SquadImportConflict(
                f"squad membership references unknown club:{observation.club_key}",
                summary=summary,
            )

        membership_id = canonical_id(
            "squad_membership",
            f"{observation.player_key}:{observation.club_key}:{observation.spell_key}",
        )
        existing = await self._session.get(SquadMembershipRecord, membership_id)
        expected = {
            "player_id": player_id,
            "club_id": club_id,
            "spell_key": observation.spell_key,
        }
        if existing is None:
            self._session.add(
                SquadMembershipRecord(
                    id=membership_id,
                    player_id=player_id,
                    club_id=club_id,
                    spell_key=observation.spell_key,
                )
            )
            summary.mark(existed=False)
        else:
            self._assert_fields(
                f"squad_membership:{observation.spell_key}",
                existing,
                expected,
                summary,
            )
            summary.mark(existed=True)
        return membership_id

    async def _persist_revision(
        self,
        membership_id: UUID,
        observation: SquadMembershipObservation,
        summary: SquadImportSummary,
    ) -> None:
        revision_id = canonical_id(
            "squad_membership_revision",
            (
                f"{observation.player_key}:{observation.club_key}:"
                f"{observation.spell_key}:{observation.revision}"
            ),
        )
        existing = await self._session.get(SquadMembershipRevisionRecord, revision_id)
        expected = {
            "membership_id": membership_id,
            "revision_number": observation.revision,
            "revision_kind": observation.revision_kind.value,
            "observed_at": observation.observed_at.astimezone(UTC),
            "valid_from": observation.valid_from.astimezone(UTC),
            "valid_until": (
                observation.valid_until.astimezone(UTC)
                if observation.valid_until is not None
                else None
            ),
            "membership_kind": observation.membership_kind.value,
            "shirt_number": observation.shirt_number,
            "reason": observation.reason,
        }
        if existing is None:
            self._session.add(
                SquadMembershipRevisionRecord(
                    id=revision_id,
                    membership_id=membership_id,
                    revision_number=observation.revision,
                    revision_kind=observation.revision_kind.value,
                    observed_at=observation.observed_at.astimezone(UTC),
                    valid_from=observation.valid_from.astimezone(UTC),
                    valid_until=(
                        observation.valid_until.astimezone(UTC)
                        if observation.valid_until is not None
                        else None
                    ),
                    membership_kind=observation.membership_kind.value,
                    shirt_number=observation.shirt_number,
                    source_id=None,
                    raw_record_id=None,
                    reason=observation.reason,
                )
            )
            summary.mark(existed=False)
            return
        self._assert_fields(
            (
                f"squad_membership_revision:{observation.spell_key}:"
                f"{observation.revision}"
            ),
            existing,
            expected,
            summary,
        )
        summary.mark(existed=True)

    @staticmethod
    def _assert_fields(
        label: str,
        record: object,
        expected: dict[str, Any],
        summary: SquadImportSummary,
    ) -> None:
        conflicts = {
            field: (getattr(record, field), value)
            for field, value in expected.items()
            if getattr(record, field) != value
        }
        if conflicts:
            summary.mark_conflict()
            raise SquadImportConflict(
                f"conflicting replay for {label}: {conflicts}",
                summary=summary,
            )
