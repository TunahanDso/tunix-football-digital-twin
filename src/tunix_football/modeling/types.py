from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite
from typing import Protocol
from uuid import UUID

Scoreline = tuple[int, int]


@dataclass(frozen=True, slots=True)
class OutcomeProbabilities:
    home_win: float
    draw: float
    away_win: float

    def __post_init__(self) -> None:
        values = (self.home_win, self.draw, self.away_win)
        if not all(isfinite(value) and 0.0 <= value <= 1.0 for value in values):
            raise ValueError("outcome probabilities must be finite values in [0, 1]")
        if abs(sum(values) - 1.0) > 1e-8:
            raise ValueError("outcome probabilities must sum to 1")

    def as_tuple(self) -> tuple[float, float, float]:
        return self.home_win, self.draw, self.away_win


@dataclass(frozen=True, slots=True)
class HistoricalMatch:
    match_id: UUID
    home_club_id: UUID
    away_club_id: UUID
    kickoff_at: datetime
    result_observed_at: datetime
    home_goals: int
    away_goals: int

    def __post_init__(self) -> None:
        if self.home_club_id == self.away_club_id:
            raise ValueError("a club cannot play itself")
        if self.home_goals < 0 or self.away_goals < 0:
            raise ValueError("goals cannot be negative")
        if self.result_observed_at < self.kickoff_at:
            raise ValueError("a result cannot be observed before kickoff")

    @property
    def outcome_index(self) -> int:
        if self.home_goals > self.away_goals:
            return 0
        if self.home_goals == self.away_goals:
            return 1
        return 2


@dataclass(frozen=True, slots=True)
class Fixture:
    match_id: UUID
    home_club_id: UUID
    away_club_id: UUID
    kickoff_at: datetime


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    match_id: UUID
    observed_at: datetime
    probabilities: OutcomeProbabilities
    source_key: str = "market"


@dataclass(frozen=True, slots=True)
class Prediction:
    probabilities: OutcomeProbabilities
    expected_home_goals: float | None = None
    expected_away_goals: float | None = None
    score_probabilities: dict[Scoreline, float] = field(default_factory=dict)


class BaselineModel(Protocol):
    key: str

    @property
    def config(self) -> dict[str, float | int | str]: ...

    def fit(self, matches: Sequence[HistoricalMatch], *, as_of: datetime) -> None: ...

    def predict(self, fixture: Fixture, *, as_of: datetime) -> Prediction: ...
