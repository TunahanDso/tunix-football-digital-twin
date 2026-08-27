from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import fmean

from tunix_football.modeling.metrics import (
    MatchMetricVector,
    calibration_bins,
    evaluate_prediction,
    expected_calibration_error,
    log_loss,
    multiclass_brier,
    ranked_probability_score,
)
from tunix_football.modeling.reproducibility import data_snapshot_hash, stable_hash
from tunix_football.modeling.types import (
    BaselineModel,
    Fixture,
    HistoricalMatch,
    MarketSnapshot,
    OutcomeProbabilities,
    Prediction,
)

ModelFactory = Callable[[], BaselineModel]


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    lead_time: timedelta
    min_train_matches: int = 50
    seed: int = 0

    def __post_init__(self) -> None:
        if self.lead_time <= timedelta(0):
            raise ValueError("lead_time must be positive")
        if self.min_train_matches < 1:
            raise ValueError("min_train_matches must be positive")


@dataclass(frozen=True, slots=True)
class BacktestObservation:
    model_key: str
    match: HistoricalMatch
    prediction_cutoff: datetime
    data_cutoff: datetime
    train_match_count: int
    model_prediction: Prediction
    model_metrics: MatchMetricVector
    market_snapshot: MarketSnapshot | None
    market_metrics: MatchMetricVector | None


@dataclass(frozen=True, slots=True)
class AggregateMetrics:
    matches: int
    log_loss: float
    brier_score: float
    ranked_probability_score: float
    score_log_loss: float | None
    ece_home: float
    ece_draw: float
    ece_away: float


@dataclass(frozen=True, slots=True)
class BacktestReport:
    model_key: str
    model_config: dict[str, float | int | str]
    config_hash: str
    data_snapshot_hash: str
    seed: int
    lead_time_seconds: int
    observations: tuple[BacktestObservation, ...]
    model_metrics: AggregateMetrics
    market_metrics: AggregateMetrics | None

    @property
    def market_coverage(self) -> int:
        return sum(item.market_metrics is not None for item in self.observations)


class WalkForwardBacktester:
    def __init__(
        self,
        *,
        model_factory: ModelFactory,
        config: BacktestConfig,
    ) -> None:
        self._model_factory = model_factory
        self._config = config

    def run(
        self,
        matches: Sequence[HistoricalMatch],
        *,
        market_snapshots: Sequence[MarketSnapshot] = (),
    ) -> BacktestReport:
        ordered = sorted(matches, key=lambda item: (item.kickoff_at, str(item.match_id)))
        if not ordered:
            raise ValueError("backtest requires historical matches")

        snapshots_by_match = self._group_market_snapshots(market_snapshots)
        observations: list[BacktestObservation] = []
        model_metadata = self._model_factory()
        model_key = model_metadata.key
        model_config = model_metadata.config

        for target in ordered:
            cutoff = target.kickoff_at - self._config.lead_time
            training = [
                match
                for match in ordered
                if match.match_id != target.match_id and match.result_observed_at <= cutoff
            ]
            if len(training) < self._config.min_train_matches:
                continue

            data_cutoff = max(match.result_observed_at for match in training)
            if data_cutoff > cutoff:
                raise AssertionError("training data crossed the prediction cutoff")

            model = self._model_factory()
            model.fit(training, as_of=cutoff)
            fixture = Fixture(
                match_id=target.match_id,
                home_club_id=target.home_club_id,
                away_club_id=target.away_club_id,
                kickoff_at=target.kickoff_at,
            )
            prediction = model.predict(fixture, as_of=cutoff)
            model_metrics = evaluate_prediction(
                prediction,
                outcome_index=target.outcome_index,
                actual_score=(target.home_goals, target.away_goals),
            )

            market = self._latest_market_at_or_before(
                snapshots_by_match.get(target.match_id, ()),
                cutoff=cutoff,
            )
            market_metrics = self._market_metrics(target, market)
            observations.append(
                BacktestObservation(
                    model_key=model.key,
                    match=target,
                    prediction_cutoff=cutoff,
                    data_cutoff=data_cutoff,
                    train_match_count=len(training),
                    model_prediction=prediction,
                    model_metrics=model_metrics,
                    market_snapshot=market,
                    market_metrics=market_metrics,
                )
            )

        if not observations:
            raise ValueError("no matches satisfied the walk-forward training requirements")

        model_aggregate = self._aggregate_model(observations)
        market_aggregate = self._aggregate_market(observations)
        experiment_config = {
            "model_key": model_key,
            "model_config": model_config,
            "lead_time_seconds": int(self._config.lead_time.total_seconds()),
            "min_train_matches": self._config.min_train_matches,
            "seed": self._config.seed,
            "market_alignment": "latest_snapshot_at_or_before_prediction_cutoff",
        }
        return BacktestReport(
            model_key=model_key,
            model_config=model_config,
            config_hash=stable_hash(experiment_config),
            data_snapshot_hash=data_snapshot_hash(ordered),
            seed=self._config.seed,
            lead_time_seconds=int(self._config.lead_time.total_seconds()),
            observations=tuple(observations),
            model_metrics=model_aggregate,
            market_metrics=market_aggregate,
        )

    @staticmethod
    def _group_market_snapshots(
        snapshots: Sequence[MarketSnapshot],
    ) -> dict[object, tuple[MarketSnapshot, ...]]:
        grouped: defaultdict[object, list[MarketSnapshot]] = defaultdict(list)
        for snapshot in snapshots:
            grouped[snapshot.match_id].append(snapshot)
        return {
            match_id: tuple(sorted(items, key=lambda item: item.observed_at))
            for match_id, items in grouped.items()
        }

    @staticmethod
    def _latest_market_at_or_before(
        snapshots: Sequence[MarketSnapshot],
        *,
        cutoff: datetime,
    ) -> MarketSnapshot | None:
        eligible = [snapshot for snapshot in snapshots if snapshot.observed_at <= cutoff]
        if not eligible:
            return None
        return max(eligible, key=lambda item: item.observed_at)

    @staticmethod
    def _market_metrics(
        target: HistoricalMatch,
        market: MarketSnapshot | None,
    ) -> MatchMetricVector | None:
        if market is None:
            return None
        probabilities = market.probabilities
        return MatchMetricVector(
            log_loss=log_loss(probabilities, target.outcome_index),
            brier_score=multiclass_brier(probabilities, target.outcome_index),
            ranked_probability_score=ranked_probability_score(
                probabilities,
                target.outcome_index,
            ),
        )

    @classmethod
    def _aggregate_model(
        cls,
        observations: Sequence[BacktestObservation],
    ) -> AggregateMetrics:
        probabilities = [item.model_prediction.probabilities for item in observations]
        outcomes = [item.match.outcome_index for item in observations]
        metrics = [item.model_metrics for item in observations]
        return cls._aggregate(metrics, probabilities, outcomes)

    @classmethod
    def _aggregate_market(
        cls,
        observations: Sequence[BacktestObservation],
    ) -> AggregateMetrics | None:
        aligned = [
            item
            for item in observations
            if item.market_metrics is not None and item.market_snapshot is not None
        ]
        if not aligned:
            return None
        metrics = [item.market_metrics for item in aligned if item.market_metrics is not None]
        probabilities = [
            item.market_snapshot.probabilities
            for item in aligned
            if item.market_snapshot is not None
        ]
        outcomes = [item.match.outcome_index for item in aligned]
        return cls._aggregate(metrics, probabilities, outcomes)

    @staticmethod
    def _aggregate(
        metrics: Sequence[MatchMetricVector],
        probabilities: Sequence[OutcomeProbabilities],
        outcomes: Sequence[int],
    ) -> AggregateMetrics:
        if not metrics:
            raise ValueError("cannot aggregate an empty metric set")
        score_losses = [item.score_log_loss for item in metrics if item.score_log_loss is not None]
        eces = []
        for outcome_class in range(3):
            pairs = [
                (probability.as_tuple()[outcome_class], outcome == outcome_class)
                for probability, outcome in zip(probabilities, outcomes, strict=True)
            ]
            eces.append(expected_calibration_error(calibration_bins(pairs)))
        return AggregateMetrics(
            matches=len(metrics),
            log_loss=fmean(item.log_loss for item in metrics),
            brier_score=fmean(item.brier_score for item in metrics),
            ranked_probability_score=fmean(item.ranked_probability_score for item in metrics),
            score_log_loss=fmean(score_losses) if score_losses else None,
            ece_home=eces[0],
            ece_draw=eces[1],
            ece_away=eces[2],
        )
