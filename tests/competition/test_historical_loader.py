from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tunix_football.competition.contracts import FixtureStatus
from tunix_football.competition.loader import (
    CompetitionSeedError,
    FixtureTimeline,
    HistoricalCompetitionLoader,
    LoadedHistoricalSeason,
)

ROOT = Path(__file__).resolve().parents[2]
SEED_PATH = ROOT / "data/competitions/tr_super_lig_2024_25.json"
FIXTURE_PATH = ROOT / "data/fixtures/tr_super_lig_2024_25_history_sample.json"


def _timeline(season: LoadedHistoricalSeason, fixture_key: str) -> FixtureTimeline:
    return next(item for item in season.fixtures if item.fixture_key == fixture_key)


def test_super_lig_seed_is_data_driven() -> None:
    loader = HistoricalCompetitionLoader()
    competition = loader.load_seed(SEED_PATH)
    season = competition.seasons[0]

    assert competition.key == "tr_super_lig"
    assert competition.timezone == "Europe/Istanbul"
    assert season.key == "2024-25"
    assert len(season.participants) == 19
    assert season.rules.round_robin_legs == 2
    assert season.rules.relegation_places == 4
    assert season.rules.promotion_places_into_season == 3

    promoted = {item.club_key for item in season.participants if item.entry == "promoted"}
    relegated = {item.club_key for item in season.participants if item.exit == "relegated"}
    assert promoted == {"eyupspor", "goztepe", "bodrum_fk"}
    assert relegated == {"adana_demirspor", "hatayspor", "sivasspor", "bodrum_fk"}


def test_historical_stream_preserves_postponement_timeline() -> None:
    loader = HistoricalCompetitionLoader()
    competition = loader.load_seed(SEED_PATH)
    season = loader.load_fixture_stream(FIXTURE_PATH, competition=competition)
    timeline = _timeline(season, "2024-25-galatasaray-gaziantep-03")

    postponed = timeline.latest_as_of(datetime(2024, 8, 16, 16, 0, tzinfo=UTC))
    rescheduled = timeline.latest_as_of(datetime(2024, 9, 4, 14, 0, tzinfo=UTC))
    finished = timeline.latest

    assert postponed is not None
    assert postponed.status is FixtureStatus.POSTPONED
    assert postponed.kickoff_at is None
    assert rescheduled is not None
    assert rescheduled.status is FixtureStatus.SCHEDULED
    assert rescheduled.kickoff_at_utc == datetime(2024, 9, 17, 17, 0, tzinfo=UTC)
    assert finished.status is FixtureStatus.FINISHED
    assert (finished.home_score, finished.away_score) == (3, 1)


def test_abandoned_match_does_not_rewrite_what_was_known() -> None:
    loader = HistoricalCompetitionLoader()
    competition = loader.load_seed(SEED_PATH)
    season = loader.load_fixture_stream(FIXTURE_PATH, competition=competition)
    timeline = _timeline(season, "2024-25-galatasaray-adana-demirspor-23")

    during_review = timeline.latest_as_of(datetime(2025, 2, 10, 12, 0, tzinfo=UTC))
    after_decision = timeline.latest_as_of(datetime(2025, 2, 13, 18, 0, tzinfo=UTC))

    assert during_review is not None
    assert during_review.status is FixtureStatus.ABANDONED
    assert (during_review.home_score, during_review.away_score) == (1, 0)
    assert after_decision is not None
    assert after_decision.status is FixtureStatus.AWARDED
    assert (after_decision.home_score, after_decision.away_score) == (3, 0)


def test_fixture_stream_rejects_non_participant_club(tmp_path: Path) -> None:
    loader = HistoricalCompetitionLoader()
    competition = loader.load_seed(SEED_PATH)
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["observations"][0]["away_club_key"] = "not_in_this_season"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CompetitionSeedError, match="non-participant"):
        loader.load_fixture_stream(path, competition=competition)


def test_cutoff_must_be_timezone_aware() -> None:
    loader = HistoricalCompetitionLoader()
    competition = loader.load_seed(SEED_PATH)
    season = loader.load_fixture_stream(FIXTURE_PATH, competition=competition)
    timeline = _timeline(season, "2024-25-galatasaray-hatayspor-01")

    with pytest.raises(ValueError, match="timezone-aware"):
        timeline.latest_as_of(datetime(2024, 8, 9, 12, 0))
