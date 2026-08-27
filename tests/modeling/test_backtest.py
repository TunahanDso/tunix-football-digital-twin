from datetime import UTC, datetime, timedelta
from uuid import uuid4

from tunix_football.modeling.backtest import BacktestConfig, WalkForwardBacktester
from tunix_football.modeling.reproducibility import data_snapshot_hash, stable_hash
from tunix_football.modeling.types import (
    Fixture,
    HistoricalMatch,
    MarketSnapshot,
    OutcomeProbabilities,
    Prediction,
)


def _history() -> list[HistoricalMatch]:
    club_a = uuid4()
    club_b = uuid4()
    start = datetime(2026, 7, 1, 19, 0, tzinfo=UTC)
    scores = [(1, 0), (0, 0), (2, 1), (0, 1), (3, 1), (1, 1)]
    return [
        HistoricalMatch(
            match_id=uuid4(),
            home_club_id=club_a if index % 2 == 0 else club_b,
            away_club_id=club_b if index % 2 == 0 else club_a,
            kickoff_at=start + timedelta(days=index * 7),
            result_observed_at=start + timedelta(days=index * 7, hours=2),
            home_goals=score[0],
            away_goals=score[1],
        )
        for index, score in enumerate(scores)
    ]


def test_walk_forward_never_trains_past_prediction_cutoff() -> None:
    matches = _history()
    seen_cutoffs: list[tuple[datetime, datetime]] = []

    class RecordingModel:
        key = "recording"
        config = {"kind": "fixed"}

        def fit(self, history, *, as_of):
            seen_cutoffs.append((max(item.result_observed_at for item in history), as_of))

        def predict(self, fixture: Fixture, *, as_of: datetime) -> Prediction:
            return Prediction(OutcomeProbabilities(0.4, 0.3, 0.3))

    report = WalkForwardBacktester(
        model_factory=RecordingModel,
        config=BacktestConfig(lead_time=timedelta(days=1), min_train_matches=2),
    ).run(matches)

    assert report.observations
    assert all(data_cutoff <= prediction_cutoff for data_cutoff, prediction_cutoff in seen_cutoffs)
    assert all(
        item.data_cutoff <= item.prediction_cutoff
        for item in report.observations
    )


def test_market_benchmark_uses_same_information_cutoff_not_closing_snapshot() -> None:
    matches = _history()
    target = matches[-1]
    cutoff = target.kickoff_at - timedelta(days=1)
    early = MarketSnapshot(
        match_id=target.match_id,
        observed_at=cutoff - timedelta(minutes=15),
        probabilities=OutcomeProbabilities(0.45, 0.30, 0.25),
        source_key="pinnacle",
    )
    closing = MarketSnapshot(
        match_id=target.match_id,
        observed_at=target.kickoff_at - timedelta(minutes=5),
        probabilities=OutcomeProbabilities(0.65, 0.20, 0.15),
        source_key="pinnacle",
    )

    class FixedModel:
        key = "fixed"
        config = {"probability": 0.4}

        def fit(self, history, *, as_of):
            return None

        def predict(self, fixture: Fixture, *, as_of: datetime) -> Prediction:
            return Prediction(OutcomeProbabilities(0.4, 0.3, 0.3))

    report = WalkForwardBacktester(
        model_factory=FixedModel,
        config=BacktestConfig(lead_time=timedelta(days=1), min_train_matches=2),
    ).run(matches, market_snapshots=[early, closing])
    target_observation = next(
        item for item in report.observations if item.match.match_id == target.match_id
    )

    assert target_observation.prediction_cutoff == cutoff
    assert target_observation.market_snapshot == early
    assert target_observation.market_snapshot != closing
    assert target_observation.market_snapshot.observed_at <= cutoff


def test_experiment_hashes_are_order_stable() -> None:
    matches = _history()

    assert data_snapshot_hash(matches) == data_snapshot_hash(list(reversed(matches)))
    assert stable_hash({"b": 2, "a": 1}) == stable_hash({"a": 1, "b": 2})
