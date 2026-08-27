from __future__ import annotations

from dataclasses import dataclass
from math import log
from random import Random
from statistics import fmean
from typing import Iterable, Sequence

from tunix_football.modeling.types import OutcomeProbabilities, Prediction, Scoreline

_EPSILON = 1e-15


@dataclass(frozen=True, slots=True)
class CalibrationBin:
    lower: float
    upper: float
    count: int
    mean_prediction: float
    empirical_frequency: float

    @property
    def absolute_gap(self) -> float:
        return abs(self.mean_prediction - self.empirical_frequency)


@dataclass(frozen=True, slots=True)
class MatchMetricVector:
    log_loss: float
    brier_score: float
    ranked_probability_score: float
    score_log_loss: float | None = None


@dataclass(frozen=True, slots=True)
class PairedBootstrapDelta:
    pairs: int
    mean_delta: float
    lower_95: float
    upper_95: float


def log_loss(probabilities: OutcomeProbabilities, outcome_index: int) -> float:
    values = probabilities.as_tuple()
    if outcome_index not in (0, 1, 2):
        raise ValueError("outcome_index must be 0, 1 or 2")
    return -log(max(values[outcome_index], _EPSILON))


def multiclass_brier(probabilities: OutcomeProbabilities, outcome_index: int) -> float:
    if outcome_index not in (0, 1, 2):
        raise ValueError("outcome_index must be 0, 1 or 2")
    values = probabilities.as_tuple()
    return sum(
        (probability - (1.0 if index == outcome_index else 0.0)) ** 2
        for index, probability in enumerate(values)
    ) / 3.0


def ranked_probability_score(
    probabilities: OutcomeProbabilities,
    outcome_index: int,
) -> float:
    if outcome_index not in (0, 1, 2):
        raise ValueError("outcome_index must be 0, 1 or 2")
    predicted = probabilities.as_tuple()
    observed = tuple(1.0 if index == outcome_index else 0.0 for index in range(3))
    predicted_cumulative = (predicted[0], predicted[0] + predicted[1])
    observed_cumulative = (observed[0], observed[0] + observed[1])
    return sum(
        (prediction - truth) ** 2
        for prediction, truth in zip(
            predicted_cumulative,
            observed_cumulative,
            strict=True,
        )
    ) / 2.0


def score_log_loss(score_probabilities: dict[Scoreline, float], actual: Scoreline) -> float:
    if not score_probabilities:
        raise ValueError("score probabilities are required")
    return -log(max(score_probabilities.get(actual, 0.0), _EPSILON))


def evaluate_prediction(
    prediction: Prediction,
    *,
    outcome_index: int,
    actual_score: Scoreline,
) -> MatchMetricVector:
    score_loss = None
    if prediction.score_probabilities:
        score_loss = score_log_loss(prediction.score_probabilities, actual_score)
    return MatchMetricVector(
        log_loss=log_loss(prediction.probabilities, outcome_index),
        brier_score=multiclass_brier(prediction.probabilities, outcome_index),
        ranked_probability_score=ranked_probability_score(
            prediction.probabilities,
            outcome_index,
        ),
        score_log_loss=score_loss,
    )


def calibration_bins(
    pairs: Iterable[tuple[float, bool]],
    *,
    bins: int = 10,
) -> list[CalibrationBin]:
    if bins <= 1:
        raise ValueError("bins must be greater than 1")
    buckets: list[list[tuple[float, bool]]] = [[] for _ in range(bins)]
    for probability, occurred in pairs:
        if not 0.0 <= probability <= 1.0:
            raise ValueError("calibration probability must be in [0, 1]")
        index = min(int(probability * bins), bins - 1)
        buckets[index].append((probability, occurred))

    output: list[CalibrationBin] = []
    for index, bucket in enumerate(buckets):
        if not bucket:
            continue
        count = len(bucket)
        mean_prediction = sum(probability for probability, _ in bucket) / count
        empirical_frequency = sum(1.0 for _, occurred in bucket if occurred) / count
        output.append(
            CalibrationBin(
                lower=index / bins,
                upper=(index + 1) / bins,
                count=count,
                mean_prediction=mean_prediction,
                empirical_frequency=empirical_frequency,
            )
        )
    return output


def expected_calibration_error(calibration: Iterable[CalibrationBin]) -> float:
    items = list(calibration)
    total = sum(item.count for item in items)
    if total == 0:
        raise ValueError("calibration bins cannot be empty")
    return sum(item.count * item.absolute_gap for item in items) / total


def paired_bootstrap_delta(
    model_scores: Sequence[float],
    benchmark_scores: Sequence[float],
    *,
    seed: int,
    samples: int = 1000,
) -> PairedBootstrapDelta:
    if len(model_scores) != len(benchmark_scores):
        raise ValueError("paired bootstrap inputs must have equal length")
    if not model_scores:
        raise ValueError("paired bootstrap requires at least one pair")
    if samples < 100:
        raise ValueError("paired bootstrap requires at least 100 samples")

    deltas = [
        model - benchmark
        for model, benchmark in zip(model_scores, benchmark_scores, strict=True)
    ]
    rng = Random(seed)
    bootstrapped: list[float] = []
    for _ in range(samples):
        draw = [deltas[rng.randrange(len(deltas))] for _ in range(len(deltas))]
        bootstrapped.append(fmean(draw))
    bootstrapped.sort()
    lower_index = int((samples - 1) * 0.025)
    upper_index = int((samples - 1) * 0.975)
    return PairedBootstrapDelta(
        pairs=len(deltas),
        mean_delta=fmean(deltas),
        lower_95=bootstrapped[lower_index],
        upper_95=bootstrapped[upper_index],
    )
