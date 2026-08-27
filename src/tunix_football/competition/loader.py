from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from tunix_football.competition.contracts import (
    CompetitionSeed,
    FixtureObservation,
    FixtureStream,
    SeasonSeed,
)


class CompetitionSeedError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class FixtureTimeline:
    fixture_key: str
    observations: tuple[FixtureObservation, ...]

    def latest_as_of(self, cutoff: datetime) -> FixtureObservation | None:
        if cutoff.tzinfo is None:
            raise ValueError("cutoff must be timezone-aware")
        eligible = [item for item in self.observations if item.observed_at <= cutoff]
        if not eligible:
            return None
        return max(eligible, key=lambda item: item.revision)

    @property
    def latest(self) -> FixtureObservation:
        return max(self.observations, key=lambda item: item.revision)


@dataclass(frozen=True, slots=True)
class LoadedHistoricalSeason:
    competition: CompetitionSeed
    season: SeasonSeed
    fixtures: tuple[FixtureTimeline, ...]


class HistoricalCompetitionLoader:
    def load_seed(self, path: str | Path) -> CompetitionSeed:
        payload = self._load_json(path)
        try:
            return CompetitionSeed.model_validate(payload)
        except ValidationError as exc:
            raise CompetitionSeedError(f"invalid competition seed: {exc}") from exc

    def load_fixture_stream(
        self,
        path: str | Path,
        *,
        competition: CompetitionSeed,
    ) -> LoadedHistoricalSeason:
        payload = self._load_json(path)
        try:
            stream = FixtureStream.model_validate(payload)
        except ValidationError as exc:
            raise CompetitionSeedError(f"invalid fixture stream: {exc}") from exc

        if stream.competition_key != competition.key:
            raise CompetitionSeedError("fixture stream competition key does not match seed")
        season = self._season(competition, stream.season_key)
        participant_keys = {participant.club_key for participant in season.participants}
        for observation in stream.observations:
            if observation.home_club_key not in participant_keys:
                raise CompetitionSeedError(
                    f"fixture references non-participant club: {observation.home_club_key}"
                )
            if observation.away_club_key not in participant_keys:
                raise CompetitionSeedError(
                    f"fixture references non-participant club: {observation.away_club_key}"
                )

        timelines = self._timelines(stream.observations)
        return LoadedHistoricalSeason(
            competition=competition,
            season=season,
            fixtures=timelines,
        )

    @staticmethod
    def _season(competition: CompetitionSeed, season_key: str) -> SeasonSeed:
        matches = [season for season in competition.seasons if season.key == season_key]
        if len(matches) != 1:
            raise CompetitionSeedError(f"unknown or duplicate season: {season_key}")
        return matches[0]

    @staticmethod
    def _timelines(
        observations: Iterable[FixtureObservation],
    ) -> tuple[FixtureTimeline, ...]:
        grouped: dict[str, list[FixtureObservation]] = {}
        for observation in observations:
            grouped.setdefault(observation.fixture_key, []).append(observation)
        return tuple(
            FixtureTimeline(
                fixture_key=fixture_key,
                observations=tuple(sorted(items, key=lambda item: item.revision)),
            )
            for fixture_key, items in sorted(grouped.items())
        )

    @staticmethod
    def _load_json(path: str | Path) -> object:
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CompetitionSeedError(f"cannot load JSON from {path}: {exc}") from exc
