from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import exp, factorial
from typing import Sequence
from uuid import UUID

from tunix_football.modeling.types import (
    Fixture,
    HistoricalMatch,
    OutcomeProbabilities,
    Prediction,
    Scoreline,
)


class EloModel:
    key = "elo"

    def __init__(
        self,
        *,
        initial_rating: float = 1500.0,
        k_factor: float = 20.0,
        home_advantage: float = 65.0,
        base_draw_probability: float = 0.27,
        draw_decay: float = 600.0,
    ) -> None:
        self._initial_rating = initial_rating
        self._k_factor = k_factor
        self._home_advantage = home_advantage
        self._base_draw_probability = base_draw_probability
        self._draw_decay = draw_decay
        self._ratings: dict[UUID, float] = {}

    @property
    def config(self) -> dict[str, float | int | str]:
        return {
            "initial_rating": self._initial_rating,
            "k_factor": self._k_factor,
            "home_advantage": self._home_advantage,
            "base_draw_probability": self._base_draw_probability,
            "draw_decay": self._draw_decay,
        }

    def fit(self, matches: Sequence[HistoricalMatch], *, as_of: datetime) -> None:
        self._ratings = {}
        for match in sorted(matches, key=lambda item: (item.result_observed_at, item.kickoff_at)):
            if match.result_observed_at > as_of:
                raise ValueError("Elo fit received information observed after the data cutoff")
            home_rating = self._rating(match.home_club_id)
            away_rating = self._rating(match.away_club_id)
            expected_home = self._expected_home_score(home_rating, away_rating)
            actual_home = self._actual_home_score(match)
            delta = self._k_factor * (actual_home - expected_home)
            self._ratings[match.home_club_id] = home_rating + delta
            self._ratings[match.away_club_id] = away_rating - delta

    def predict(self, fixture: Fixture, *, as_of: datetime) -> Prediction:
        if fixture.kickoff_at <= as_of:
            raise ValueError("prediction cutoff must be earlier than fixture kickoff")
        home_rating = self._rating(fixture.home_club_id)
        away_rating = self._rating(fixture.away_club_id)
        expected_home = self._expected_home_score(home_rating, away_rating)
        rating_gap = abs((home_rating + self._home_advantage) - away_rating)
        draw = self._base_draw_probability * exp(-rating_gap / self._draw_decay)
        draw = min(max(draw, 0.05), 0.35)
        remaining = 1.0 - draw
        probabilities = OutcomeProbabilities(
            home_win=remaining * expected_home,
            draw=draw,
            away_win=remaining * (1.0 - expected_home),
        )
        return Prediction(probabilities=probabilities)

    def _rating(self, club_id: UUID) -> float:
        return self._ratings.get(club_id, self._initial_rating)

    def _expected_home_score(self, home_rating: float, away_rating: float) -> float:
        gap = (home_rating + self._home_advantage) - away_rating
        return 1.0 / (1.0 + 10.0 ** (-gap / 400.0))

    @staticmethod
    def _actual_home_score(match: HistoricalMatch) -> float:
        if match.home_goals > match.away_goals:
            return 1.0
        if match.home_goals == match.away_goals:
            return 0.5
        return 0.0


@dataclass(slots=True)
class _VenueStats:
    matches: int = 0
    goals_for: int = 0
    goals_against: int = 0


class IndependentPoissonModel:
    key = "poisson"

    def __init__(
        self,
        *,
        smoothing_matches: float = 3.0,
        max_goals: int = 8,
        min_lambda: float = 0.05,
        max_lambda: float = 5.0,
    ) -> None:
        if smoothing_matches <= 0:
            raise ValueError("smoothing_matches must be positive")
        if max_goals < 3:
            raise ValueError("max_goals must be at least 3")
        self._smoothing_matches = smoothing_matches
        self._max_goals = max_goals
        self._min_lambda = min_lambda
        self._max_lambda = max_lambda
        self._home_stats: dict[UUID, _VenueStats] = {}
        self._away_stats: dict[UUID, _VenueStats] = {}
        self._league_home_mean = 1.35
        self._league_away_mean = 1.10
        self._fitted = False

    @property
    def config(self) -> dict[str, float | int | str]:
        return {
            "smoothing_matches": self._smoothing_matches,
            "max_goals": self._max_goals,
            "min_lambda": self._min_lambda,
            "max_lambda": self._max_lambda,
        }

    def fit(self, matches: Sequence[HistoricalMatch], *, as_of: datetime) -> None:
        if not matches:
            raise ValueError("Poisson fit requires at least one historical match")
        self._home_stats = {}
        self._away_stats = {}
        total_home_goals = 0
        total_away_goals = 0

        for match in matches:
            if match.result_observed_at > as_of:
                raise ValueError("Poisson fit received information observed after the data cutoff")
            home = self._home_stats.setdefault(match.home_club_id, _VenueStats())
            away = self._away_stats.setdefault(match.away_club_id, _VenueStats())
            home.matches += 1
            home.goals_for += match.home_goals
            home.goals_against += match.away_goals
            away.matches += 1
            away.goals_for += match.away_goals
            away.goals_against += match.home_goals
            total_home_goals += match.home_goals
            total_away_goals += match.away_goals

        count = float(len(matches))
        self._league_home_mean = max(total_home_goals / count, self._min_lambda)
        self._league_away_mean = max(total_away_goals / count, self._min_lambda)
        self._fitted = True

    def predict(self, fixture: Fixture, *, as_of: datetime) -> Prediction:
        if not self._fitted:
            raise RuntimeError("fit must be called before predict")
        if fixture.kickoff_at <= as_of:
            raise ValueError("prediction cutoff must be earlier than fixture kickoff")

        home_lambda, away_lambda = self._expected_goals(fixture)
        score_probabilities = self._score_distribution(home_lambda, away_lambda)
        probabilities = self._outcomes_from_scores(score_probabilities)
        return Prediction(
            probabilities=probabilities,
            expected_home_goals=home_lambda,
            expected_away_goals=away_lambda,
            score_probabilities=score_probabilities,
        )

    def _expected_goals(self, fixture: Fixture) -> tuple[float, float]:
        home = self._home_stats.get(fixture.home_club_id, _VenueStats())
        away = self._away_stats.get(fixture.away_club_id, _VenueStats())

        home_attack = self._smoothed_ratio(
            home.goals_for,
            home.matches,
            self._league_home_mean,
        )
        home_defense = self._smoothed_ratio(
            home.goals_against,
            home.matches,
            self._league_away_mean,
        )
        away_attack = self._smoothed_ratio(
            away.goals_for,
            away.matches,
            self._league_away_mean,
        )
        away_defense = self._smoothed_ratio(
            away.goals_against,
            away.matches,
            self._league_home_mean,
        )

        home_lambda = self._clamp_lambda(self._league_home_mean * home_attack * away_defense)
        away_lambda = self._clamp_lambda(self._league_away_mean * away_attack * home_defense)
        return home_lambda, away_lambda

    def _smoothed_ratio(self, goals: int, matches: int, league_mean: float) -> float:
        numerator = goals + self._smoothing_matches * league_mean
        denominator = matches + self._smoothing_matches
        return (numerator / denominator) / league_mean

    def _clamp_lambda(self, value: float) -> float:
        return min(max(value, self._min_lambda), self._max_lambda)

    def _score_distribution(self, home_lambda: float, away_lambda: float) -> dict[Scoreline, float]:
        scores: dict[Scoreline, float] = {}
        for home_goals in range(self._max_goals + 1):
            home_pmf = self._poisson_pmf(home_goals, home_lambda)
            for away_goals in range(self._max_goals + 1):
                probability = home_pmf * self._poisson_pmf(away_goals, away_lambda)
                scores[(home_goals, away_goals)] = probability
        return self._normalize_scores(scores)

    @staticmethod
    def _poisson_pmf(goals: int, rate: float) -> float:
        return exp(-rate) * rate**goals / factorial(goals)

    @staticmethod
    def _normalize_scores(scores: dict[Scoreline, float]) -> dict[Scoreline, float]:
        total = sum(scores.values())
        if total <= 0:
            raise ValueError("score distribution has no probability mass")
        return {score: probability / total for score, probability in scores.items()}

    @staticmethod
    def _outcomes_from_scores(scores: dict[Scoreline, float]) -> OutcomeProbabilities:
        home = sum(probability for (h, a), probability in scores.items() if h > a)
        draw = sum(probability for (h, a), probability in scores.items() if h == a)
        away = sum(probability for (h, a), probability in scores.items() if h < a)
        total = home + draw + away
        return OutcomeProbabilities(home / total, draw / total, away / total)


class DixonColesModel(IndependentPoissonModel):
    key = "dixon_coles"

    def __init__(self, *, rho: float = -0.08, **kwargs: float | int) -> None:
        super().__init__(**kwargs)
        if not -0.5 < rho < 0.5:
            raise ValueError("rho must stay in a conservative correction range")
        self._rho = rho

    @property
    def config(self) -> dict[str, float | int | str]:
        values = super().config
        values["rho"] = self._rho
        return values

    def _score_distribution(self, home_lambda: float, away_lambda: float) -> dict[Scoreline, float]:
        scores = super()._score_distribution(home_lambda, away_lambda)
        corrected: dict[Scoreline, float] = {}
        for score, probability in scores.items():
            correction = self._tau(score, home_lambda, away_lambda)
            corrected[score] = max(probability * correction, 1e-15)
        return self._normalize_scores(corrected)

    def _tau(self, score: Scoreline, home_lambda: float, away_lambda: float) -> float:
        if score == (0, 0):
            return 1.0 - home_lambda * away_lambda * self._rho
        if score == (0, 1):
            return 1.0 + home_lambda * self._rho
        if score == (1, 0):
            return 1.0 + away_lambda * self._rho
        if score == (1, 1):
            return 1.0 - self._rho
        return 1.0
