from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, model_validator


class CompetitionType(StrEnum):
    LEAGUE = "league"
    CUP = "cup"
    PLAYOFF = "playoff"


class ParticipationEntry(StrEnum):
    CONTINUING = "continuing"
    PROMOTED = "promoted"
    INVITED = "invited"
    EXPANSION = "expansion"
    OTHER = "other"


class ParticipationExit(StrEnum):
    CONTINUING = "continuing"
    RELEGATED = "relegated"
    WITHDREW = "withdrew"
    EXPELLED = "expelled"
    OTHER = "other"


class FixtureStatus(StrEnum):
    SCHEDULED = "scheduled"
    POSTPONED = "postponed"
    ABANDONED = "abandoned"
    CANCELLED = "cancelled"
    FINISHED = "finished"
    AWARDED = "awarded"


class FixtureRevisionKind(StrEnum):
    INITIAL = "initial"
    SCHEDULE_CHANGE = "schedule_change"
    STATUS_CHANGE = "status_change"
    RESULT_CORRECTION = "result_correction"


class RankingRule(StrEnum):
    POINTS = "points"
    HEAD_TO_HEAD_POINTS = "head_to_head_points"
    HEAD_TO_HEAD_GOAL_DIFFERENCE = "head_to_head_goal_difference"
    HEAD_TO_HEAD_GOALS = "head_to_head_goals"
    GOAL_DIFFERENCE = "goal_difference"
    GOALS_FOR = "goals_for"
    PLAYOFF = "playoff"
    DRAWING_OF_LOTS = "drawing_of_lots"


class PointsRule(BaseModel):
    win: int = 3
    draw: int = 1
    loss: int = 0


class SeasonRules(BaseModel):
    version: int = Field(ge=1)
    points: PointsRule = Field(default_factory=PointsRule)
    ranking: list[RankingRule]
    round_robin_legs: int = Field(ge=1)
    relegation_places: int = Field(ge=0)
    promotion_places_into_season: int = Field(ge=0)
    notes: list[str] = Field(default_factory=list)


class ClubSeed(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    country_code: str = Field(min_length=3, max_length=3)


class SeasonParticipantSeed(BaseModel):
    club_key: str
    entry: ParticipationEntry
    exit: ParticipationExit = ParticipationExit.CONTINUING
    from_competition_key: str | None = None
    to_competition_key: str | None = None


class SeasonSeed(BaseModel):
    key: str
    starts_on: date
    ends_on: date
    rules: SeasonRules
    participants: list[SeasonParticipantSeed]

    @model_validator(mode="after")
    def validate_season(self) -> SeasonSeed:
        if self.ends_on <= self.starts_on:
            raise ValueError("season ends_on must be after starts_on")
        participant_keys = [item.club_key for item in self.participants]
        if len(set(participant_keys)) != len(participant_keys):
            raise ValueError("season participants must be unique")
        return self


class CompetitionSeed(BaseModel):
    format_version: int = Field(ge=1)
    key: str
    name: str
    country_code: str = Field(min_length=3, max_length=3)
    competition_type: CompetitionType
    timezone: str
    clubs: list[ClubSeed]
    seasons: list[SeasonSeed]

    @model_validator(mode="after")
    def validate_references(self) -> CompetitionSeed:
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown competition timezone: {self.timezone}") from exc

        club_keys = [club.key for club in self.clubs]
        if len(set(club_keys)) != len(club_keys):
            raise ValueError("club seed keys must be unique")
        known_clubs = set(club_keys)
        season_keys = [season.key for season in self.seasons]
        if len(set(season_keys)) != len(season_keys):
            raise ValueError("season seed keys must be unique")
        for season in self.seasons:
            missing = {
                participant.club_key
                for participant in season.participants
                if participant.club_key not in known_clubs
            }
            if missing:
                raise ValueError(f"season references unknown clubs: {sorted(missing)}")
        return self


class FixtureObservation(BaseModel):
    fixture_key: str
    revision: int = Field(ge=1)
    revision_kind: FixtureRevisionKind
    observed_at: datetime
    kickoff_at: datetime | None
    home_club_key: str
    away_club_key: str
    status: FixtureStatus
    home_score: int | None = Field(default=None, ge=0)
    away_score: int | None = Field(default=None, ge=0)
    reason: str | None = None

    @model_validator(mode="after")
    def validate_fixture(self) -> FixtureObservation:
        if self.home_club_key == self.away_club_key:
            raise ValueError("a club cannot play itself")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if self.kickoff_at is not None and self.kickoff_at.tzinfo is None:
            raise ValueError("kickoff_at must be timezone-aware")
        if self.status in {FixtureStatus.FINISHED, FixtureStatus.AWARDED}:
            if self.home_score is None or self.away_score is None:
                raise ValueError("finished and awarded fixtures require a score")
        if self.status in {
            FixtureStatus.SCHEDULED,
            FixtureStatus.POSTPONED,
            FixtureStatus.CANCELLED,
        } and (self.home_score is not None or self.away_score is not None):
            raise ValueError("non-played fixture states cannot carry a final score")
        if self.revision == 1 and self.revision_kind is not FixtureRevisionKind.INITIAL:
            raise ValueError("fixture revision 1 must be initial")
        if self.revision > 1 and self.revision_kind is FixtureRevisionKind.INITIAL:
            raise ValueError("only fixture revision 1 may be initial")
        return self

    @property
    def observed_at_utc(self) -> datetime:
        return self.observed_at.astimezone(UTC)

    @property
    def kickoff_at_utc(self) -> datetime | None:
        if self.kickoff_at is None:
            return None
        return self.kickoff_at.astimezone(UTC)


class FixtureStream(BaseModel):
    format_version: int = Field(ge=1)
    competition_key: str
    season_key: str
    observations: list[FixtureObservation]

    @model_validator(mode="after")
    def validate_revisions(self) -> FixtureStream:
        by_fixture: dict[str, list[FixtureObservation]] = {}
        for observation in self.observations:
            by_fixture.setdefault(observation.fixture_key, []).append(observation)

        for fixture_key, observations in by_fixture.items():
            ordered = sorted(observations, key=lambda item: item.revision)
            expected_revisions = list(range(1, len(ordered) + 1))
            if [item.revision for item in ordered] != expected_revisions:
                raise ValueError(f"fixture {fixture_key} revisions must be contiguous")
            observed_times = [item.observed_at_utc for item in ordered]
            if observed_times != sorted(observed_times):
                raise ValueError(f"fixture {fixture_key} observation time moved backwards")
            first = ordered[0]
            if any(
                item.home_club_key != first.home_club_key
                or item.away_club_key != first.away_club_key
                for item in ordered[1:]
            ):
                raise ValueError(f"fixture {fixture_key} changed participants across revisions")
        return self
