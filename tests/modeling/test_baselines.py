from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from tunix_football.modeling.metrics import (
    calibration_bins,
    expected_calibration_error,
    log_loss,
    multiclass_brier,
    ranked_probability_score,
)
from tunix_football.modeling.models import DixonColesModel, EloModel, IndependentPoissonModel
from tunix_football.modeling.types import Fixture, HistoricalMatch, OutcomeProbabilities


def _match(
    *,
    kickoff: datetime,
    home_goals: int,
    away_goals: int,
    home_club_id=None,
    away_club_id=None,
) -> HistoricalMatch:
    return HistoricalMatch(
        match_id=uuid4(),
        home_club_id=home_club_id or uuid4(),
        away_club_id=away_club_id or uuid4(),
        kickoff_at=kickoff,
        result_observed_at=kickoff + timedelta(hours=2),
        home_goals=home_goals,
        away_goals=away_goals,
    )


def test_proper_scores_reward_perfect_probability() -> None:
    perfect = OutcomeProbabilities(1.0, 0.0, 0.0)

    assert log_loss(perfect, 0) == pytest.approx(0.0)
    assert multiclass_brier(perfect, 0) == pytest.approx(0.0)
    assert ranked_probability_score(perfect, 0) == pytest.approx(0.0)


def test_calibration_ece_is_zero_for_exact_bins() -> None:
    bins = calibration_bins([(0.0, False), (1.0, True)], bins=2)

    assert expected_calibration_error(bins) == pytest.approx(0.0)


def test_elo_rejects_information_observed_after_cutoff() -> None:
    kickoff = datetime(2026, 8, 1, 18, 0, tzinfo=UTC)
    match = _match(kickoff=kickoff, home_goals=2, away_goals=0)

    with pytest.raises(ValueError, match="data cutoff"):
        EloModel().fit([match], as_of=kickoff + timedelta(hours=1))


def test_poisson_score_distribution_is_normalized() -> None:
    home = uuid4()
    away = uuid4()
    kickoff = datetime(2026, 8, 1, 18, 0, tzinfo=UTC)
    history = [
        _match(
            kickoff=kickoff + timedelta(days=index),
            home_goals=2 if index % 2 == 0 else 1,
            away_goals=index % 2,
            home_club_id=home,
            away_club_id=away,
        )
        for index in range(6)
    ]
    cutoff = history[-1].result_observed_at
    fixture = Fixture(
        match_id=uuid4(),
        home_club_id=home,
        away_club_id=away,
        kickoff_at=cutoff + timedelta(days=2),
    )
    model = IndependentPoissonModel()
    model.fit(history, as_of=cutoff)

    prediction = model.predict(fixture, as_of=cutoff)

    assert sum(prediction.probabilities.as_tuple()) == pytest.approx(1.0)
    assert sum(prediction.score_probabilities.values()) == pytest.approx(1.0)
    assert prediction.expected_home_goals is not None
    assert prediction.expected_away_goals is not None


def test_dixon_coles_changes_low_score_mass() -> None:
    home = uuid4()
    away = uuid4()
    kickoff = datetime(2026, 8, 1, 18, 0, tzinfo=UTC)
    history = [
        _match(
            kickoff=kickoff + timedelta(days=index),
            home_goals=index % 3,
            away_goals=(index + 1) % 2,
            home_club_id=home,
            away_club_id=away,
        )
        for index in range(8)
    ]
    cutoff = history[-1].result_observed_at
    fixture = Fixture(
        match_id=uuid4(),
        home_club_id=home,
        away_club_id=away,
        kickoff_at=cutoff + timedelta(days=2),
    )
    poisson = IndependentPoissonModel()
    dixon_coles = DixonColesModel(rho=-0.08)
    poisson.fit(history, as_of=cutoff)
    dixon_coles.fit(history, as_of=cutoff)

    poisson_prediction = poisson.predict(fixture, as_of=cutoff)
    dc_prediction = dixon_coles.predict(fixture, as_of=cutoff)

    assert dc_prediction.score_probabilities[(0, 0)] != pytest.approx(
        poisson_prediction.score_probabilities[(0, 0)]
    )
    assert sum(dc_prediction.score_probabilities.values()) == pytest.approx(1.0)
