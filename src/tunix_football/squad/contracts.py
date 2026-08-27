from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, model_validator


class MembershipKind(StrEnum):
    PERMANENT = "permanent"
    LOAN = "loan"
    ACADEMY = "academy"
    TRIAL = "trial"
    UNKNOWN = "unknown"


class MembershipRevisionKind(StrEnum):
    INITIAL = "initial"
    CORRECTION = "correction"
    WINDOW_CHANGE = "window_change"
    DETAILS_CHANGE = "details_change"


class PlayerSeed(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$", max_length=160)
    name: str = Field(min_length=1, max_length=160)
    birth_date: date | None = None
    country_code: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")


class SquadMembershipObservation(BaseModel):
    spell_key: str = Field(pattern=r"^[a-z0-9][a-z0-9._:-]*$", max_length=160)
    revision: int = Field(ge=1)
    revision_kind: MembershipRevisionKind
    observed_at: datetime
    valid_from: datetime
    valid_until: datetime | None = None
    player_key: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$", max_length=160)
    club_key: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$", max_length=160)
    membership_kind: MembershipKind = MembershipKind.UNKNOWN
    shirt_number: int | None = Field(default=None, gt=0)
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_temporal_contract(self) -> Self:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if self.valid_from.tzinfo is None or self.valid_from.utcoffset() is None:
            raise ValueError("valid_from must be timezone-aware")
        if self.valid_until is not None:
            if self.valid_until.tzinfo is None or self.valid_until.utcoffset() is None:
                raise ValueError("valid_until must be timezone-aware")
            if self.valid_until <= self.valid_from:
                raise ValueError("valid_until must be later than valid_from")
        return self


class SquadHistorySeed(BaseModel):
    format_version: int = Field(default=1, ge=1)
    players: list[PlayerSeed] = Field(min_length=1)
    observations: list[SquadMembershipObservation] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_history(self) -> Self:
        player_keys = [player.key for player in self.players]
        if len(set(player_keys)) != len(player_keys):
            raise ValueError("player keys must be unique")

        declared_players = set(player_keys)
        unknown_players = {
            observation.player_key
            for observation in self.observations
            if observation.player_key not in declared_players
        }
        if unknown_players:
            raise ValueError(
                f"observations reference undeclared players: {sorted(unknown_players)}"
            )

        revision_keys = [
            (observation.spell_key, observation.revision)
            for observation in self.observations
        ]
        if len(set(revision_keys)) != len(revision_keys):
            raise ValueError("spell revision keys must be unique")

        by_spell: dict[str, list[SquadMembershipObservation]] = defaultdict(list)
        for observation in self.observations:
            by_spell[observation.spell_key].append(observation)

        for spell_key, observations in by_spell.items():
            identities = {
                (observation.player_key, observation.club_key)
                for observation in observations
            }
            if len(identities) != 1:
                raise ValueError(
                    f"spell {spell_key} changes player or club identity across revisions"
                )

            ordered = sorted(observations, key=lambda item: item.revision)
            revisions = [item.revision for item in ordered]
            expected = list(range(1, len(ordered) + 1))
            if revisions != expected:
                raise ValueError(
                    f"spell {spell_key} revisions must be contiguous from 1"
                )
            if ordered[0].revision_kind is not MembershipRevisionKind.INITIAL:
                raise ValueError(f"spell {spell_key} revision 1 must be initial")

            observed_times = [item.observed_at for item in ordered]
            if any(
                later <= earlier
                for earlier, later in zip(
                    observed_times,
                    observed_times[1:],
                    strict=False,
                )
            ):
                raise ValueError(
                    f"spell {spell_key} observed_at must increase with revision"
                )

        return self
