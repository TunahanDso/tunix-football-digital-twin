from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tunix_football.canonical_ids import canonical_id
from tunix_football.competition.contracts import CompetitionSeed
from tunix_football.competition.loader import (
    HistoricalCompetitionLoader,
    LoadedHistoricalSeason,
)
from tunix_football.competition.persistence import (
    CanonicalHistoryWriter,
    CanonicalImportConflict,
)
from tunix_football.db.competition_models import (
    MatchRevisionRecord,
    SeasonClubParticipationRecord,
    SeasonRuleVersionRecord,
)
from tunix_football.db.models import (
    CanonicalEntity,
    Club,
    Competition,
    CompetitionSeason,
    Match,
)
from tunix_football.db.session import database_url

ROOT = Path(__file__).resolve().parents[2]
SEED_PATH = ROOT / "data/competitions/tr_super_lig_2024_25.json"
FIXTURE_PATH = ROOT / "data/fixtures/tr_super_lig_2024_25_history_sample.json"

TEST_ENGINE = create_async_engine(database_url(), poolclass=NullPool)
TestSessionFactory = async_sessionmaker(
    TEST_ENGINE,
    expire_on_commit=False,
    class_=AsyncSession,
)


@pytest_asyncio.fixture(autouse=True)
async def clean_canonical_history() -> None:
    async with TestSessionFactory() as session, session.begin():
        await session.execute(text("TRUNCATE TABLE canonical_entities CASCADE"))
    yield
    async with TestSessionFactory() as session, session.begin():
        await session.execute(text("TRUNCATE TABLE canonical_entities CASCADE"))


def _dataset() -> tuple[CompetitionSeed, LoadedHistoricalSeason]:
    loader = HistoricalCompetitionLoader()
    competition = loader.load_seed(SEED_PATH)
    history = loader.load_fixture_stream(FIXTURE_PATH, competition=competition)
    return competition, history


async def _count(model: type[object]) -> int:
    async with TestSessionFactory() as session:
        result = await session.execute(select(func.count()).select_from(model))
        return int(result.scalar_one())


@pytest.mark.asyncio
async def test_import_is_idempotent_and_preserves_temporal_truth() -> None:
    competition, history = _dataset()

    async with TestSessionFactory() as session:
        first = await CanonicalHistoryWriter(session).import_dataset(
            competition=competition,
            history=history,
        )

    assert first.inserted > 0
    assert first.existing == 0
    assert first.conflicting == 0

    counts_after_first = {
        "entities": await _count(CanonicalEntity),
        "competitions": await _count(Competition),
        "clubs": await _count(Club),
        "seasons": await _count(CompetitionSeason),
        "rules": await _count(SeasonRuleVersionRecord),
        "participations": await _count(SeasonClubParticipationRecord),
        "matches": await _count(Match),
        "revisions": await _count(MatchRevisionRecord),
    }
    assert counts_after_first == {
        "entities": 21,
        "competitions": 2,
        "clubs": 19,
        "seasons": 1,
        "rules": 1,
        "participations": 19,
        "matches": 3,
        "revisions": 9,
    }

    async with TestSessionFactory() as session:
        second = await CanonicalHistoryWriter(session).import_dataset(
            competition=competition,
            history=history,
        )

    assert second.inserted == 0
    assert second.existing == first.inserted
    assert second.conflicting == 0
    assert {
        "entities": await _count(CanonicalEntity),
        "competitions": await _count(Competition),
        "clubs": await _count(Club),
        "seasons": await _count(CompetitionSeason),
        "rules": await _count(SeasonRuleVersionRecord),
        "participations": await _count(SeasonClubParticipationRecord),
        "matches": await _count(Match),
        "revisions": await _count(MatchRevisionRecord),
    } == counts_after_first

    season_id = canonical_id("season", "tr_super_lig:2024-25")
    rule_id = canonical_id("season_rule", "tr_super_lig:2024-25:1")
    match_id = canonical_id("match", "2024-25-galatasaray-adana-demirspor-23")

    async with TestSessionFactory() as session:
        season = await session.get(CompetitionSeason, season_id)
        rule = await session.get(SeasonRuleVersionRecord, rule_id)
        match = await session.get(Match, match_id)

    assert season is not None
    assert season.competition_id == canonical_id("competition", "tr_super_lig")
    assert rule is not None
    assert rule.observed_at == datetime(2024, 7, 26, 9, 0, tzinfo=UTC)
    assert rule.valid_from == datetime(2024, 8, 8, 21, 0, tzinfo=UTC)
    assert rule.observed_at < rule.valid_from
    assert match is not None
    assert match.status == "awarded"
    assert (match.home_score, match.away_score) == (3, 0)


@pytest.mark.asyncio
async def test_later_revision_appends_without_stale_replay_rolling_state_back(
    tmp_path: Path,
) -> None:
    competition, history = _dataset()
    async with TestSessionFactory() as session:
        await CanonicalHistoryWriter(session).import_dataset(
            competition=competition,
            history=history,
        )

    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["observations"].append(
        {
            "fixture_key": "2024-25-galatasaray-hatayspor-01",
            "revision": 3,
            "revision_kind": "result_correction",
            "observed_at": "2024-08-10T12:00:00+03:00",
            "kickoff_at": "2024-08-09T21:00:00+03:00",
            "home_club_key": "galatasaray",
            "away_club_key": "hatayspor",
            "status": "finished",
            "home_score": 2,
            "away_score": 0,
            "reason": "Synthetic correction used to verify append-only persistence",
        }
    )
    extended_path = tmp_path / "extended-history.json"
    extended_path.write_text(json.dumps(payload), encoding="utf-8")
    loader = HistoricalCompetitionLoader()
    extended = loader.load_fixture_stream(extended_path, competition=competition)

    async with TestSessionFactory() as session:
        summary = await CanonicalHistoryWriter(session).import_dataset(
            competition=competition,
            history=extended,
        )

    assert summary.inserted == 1
    assert summary.conflicting == 0

    match_id = canonical_id("match", "2024-25-galatasaray-hatayspor-01")
    async with TestSessionFactory() as session:
        match = await session.get(Match, match_id)
        revision_count_result = await session.execute(
            select(func.count())
            .select_from(MatchRevisionRecord)
            .where(MatchRevisionRecord.match_id == match_id)
        )
        revision_count = int(revision_count_result.scalar_one())

    assert revision_count == 3
    assert match is not None
    assert (match.home_score, match.away_score) == (2, 0)

    async with TestSessionFactory() as session:
        stale_summary = await CanonicalHistoryWriter(session).import_dataset(
            competition=competition,
            history=history,
        )
    assert stale_summary.inserted == 0

    async with TestSessionFactory() as session:
        current = await session.get(Match, match_id)
    assert current is not None
    assert (current.home_score, current.away_score) == (2, 0)


@pytest.mark.asyncio
async def test_conflicting_replay_is_auditable_and_rolls_back_partial_writes() -> None:
    competition, history = _dataset()
    async with TestSessionFactory() as session:
        await CanonicalHistoryWriter(session).import_dataset(
            competition=competition,
            history=history,
        )

    baseline_competitions = await _count(Competition)
    baseline_entities = await _count(CanonicalEntity)

    payload = competition.model_dump(mode="json")
    payload["related_competitions"].append(
        {
            "key": "rollback_probe",
            "name": "Rollback Probe League",
            "country_code": "TUR",
            "competition_type": "league",
        }
    )
    payload["clubs"][0]["name"] = "Conflicting Adana Demirspor Name"
    conflicting_seed = CompetitionSeed.model_validate(payload)

    async with TestSessionFactory() as session:
        with pytest.raises(CanonicalImportConflict, match="conflicting replay for club") as exc:
            await CanonicalHistoryWriter(session).import_dataset(
                competition=conflicting_seed,
                history=history,
            )

    assert exc.value.summary.conflicting == 1
    assert exc.value.summary.inserted >= 2
    assert await _count(Competition) == baseline_competitions
    assert await _count(CanonicalEntity) == baseline_entities

    rollback_probe_id = canonical_id("competition", "rollback_probe")
    async with TestSessionFactory() as session:
        probe = await session.get(Competition, rollback_probe_id)
    assert probe is None
