from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tunix_football.canonical_ids import canonical_id
from tunix_football.db.base import Base
from tunix_football.db.models import CanonicalEntity, Club, Player
from tunix_football.db.session import database_url
from tunix_football.db.squad_models import (
    SquadMembershipRecord,
    SquadMembershipRevisionRecord,
)
from tunix_football.squad.contracts import (
    SquadHistorySeed,
    SquadMembershipObservation,
)
from tunix_football.squad.loader import load_squad_history
from tunix_football.squad.persistence import SquadHistoryWriter, SquadImportConflict
from tunix_football.squad.query import SquadMemberSnapshot, SquadQuery

ROOT = Path(__file__).resolve().parents[2]
SQUAD_PATH = ROOT / "tests/fixtures/temporal_squad_history.json"

TEST_ENGINE = create_async_engine(database_url(), poolclass=NullPool)
TestSessionFactory = async_sessionmaker(
    TEST_ENGINE,
    expire_on_commit=False,
    class_=AsyncSession,
)


@pytest_asyncio.fixture(autouse=True)
async def clean_temporal_squad_history() -> None:
    async with TestSessionFactory() as session, session.begin():
        await session.execute(text("TRUNCATE TABLE canonical_entities CASCADE"))
    yield
    async with TestSessionFactory() as session, session.begin():
        await session.execute(text("TRUNCATE TABLE canonical_entities CASCADE"))


async def _seed_clubs() -> None:
    clubs = (
        ("galatasaray", "Galatasaray"),
        ("fenerbahce", "Fenerbahçe"),
    )
    async with TestSessionFactory() as session, session.begin():
        for key, name in clubs:
            entity_id = canonical_id("club", key)
            session.add(
                CanonicalEntity(
                    id=entity_id,
                    entity_type="club",
                    retired_at=None,
                )
            )
            session.add(
                Club(
                    entity_id=entity_id,
                    canonical_name=name,
                    short_name=None,
                    country_code="TUR",
                )
            )


async def _count(model: type[object]) -> int:
    async with TestSessionFactory() as session:
        result = await session.execute(select(func.count()).select_from(model))
        return int(result.scalar_one())


def _seed() -> SquadHistorySeed:
    return load_squad_history(SQUAD_PATH)


def _names(snapshots: list[SquadMemberSnapshot]) -> set[str]:
    return {snapshot.player_name for snapshot in snapshots}


def test_squad_schema_has_temporal_database_guards() -> None:
    membership_columns = set(
        Base.metadata.tables["player_squad_memberships"].columns.keys()
    )
    revision_table = Base.metadata.tables["player_squad_membership_revisions"]
    revision_columns = set(revision_table.columns.keys())
    check_names = {
        constraint.name
        for constraint in revision_table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    player_columns = set(Base.metadata.tables["players"].columns.keys())

    assert {"id", "player_id", "club_id", "spell_key"} <= membership_columns
    assert {
        "membership_id",
        "revision_number",
        "observed_at",
        "valid_from",
        "valid_until",
        "source_id",
        "raw_record_id",
    } <= revision_columns
    assert "ck_player_squad_membership_revisions_positive_revision" in check_names
    assert "ck_player_squad_membership_revisions_valid_time_window" in check_names
    assert "current_club_id" not in player_columns
    assert "source_id" not in player_columns
    assert "external_id" not in player_columns


def test_contract_allows_both_knowledge_time_directions_and_rejects_bad_window() -> None:
    seed = _seed()
    future = next(item for item in seed.observations if item.player_key == "future_player")
    late = next(item for item in seed.observations if item.player_key == "late_player")

    assert future.observed_at < future.valid_from
    assert late.observed_at > late.valid_from

    payload = future.model_dump(mode="json")
    payload["valid_until"] = payload["valid_from"]
    with pytest.raises(ValidationError, match="valid_until must be later than valid_from"):
        SquadMembershipObservation.model_validate(payload)


@pytest.mark.asyncio
async def test_import_creates_stable_players_spells_and_append_only_revisions() -> None:
    await _seed_clubs()
    seed = _seed()

    async with TestSessionFactory() as session:
        summary = await SquadHistoryWriter(session).import_dataset(seed)

    assert summary.inserted == 19
    assert summary.existing == 0
    assert summary.conflicting == 0
    assert await _count(CanonicalEntity) == 6
    assert await _count(Player) == 4
    assert await _count(SquadMembershipRecord) == 5
    assert await _count(SquadMembershipRevisionRecord) == 6

    traveler_id = canonical_id("player", "traveler")
    async with TestSessionFactory() as session:
        traveler = await session.get(Player, traveler_id)
        result = await session.execute(
            select(func.count())
            .select_from(SquadMembershipRecord)
            .where(SquadMembershipRecord.player_id == traveler_id)
        )
        traveler_spells = int(result.scalar_one())

    assert traveler is not None
    assert traveler.canonical_name == "Traveler Player"
    assert traveler_spells == 2


@pytest.mark.asyncio
async def test_identical_replay_is_idempotent() -> None:
    await _seed_clubs()
    seed = _seed()
    async with TestSessionFactory() as session:
        first = await SquadHistoryWriter(session).import_dataset(seed)

    async with TestSessionFactory() as session:
        second = await SquadHistoryWriter(session).import_dataset(seed)

    assert first.inserted == 19
    assert second.inserted == 0
    assert second.existing == first.inserted
    assert second.conflicting == 0
    assert await _count(Player) == 4
    assert await _count(SquadMembershipRecord) == 5
    assert await _count(SquadMembershipRevisionRecord) == 6


@pytest.mark.asyncio
async def test_later_revision_appends_and_stale_replay_cannot_remove_it() -> None:
    await _seed_clubs()
    seed = _seed()
    async with TestSessionFactory() as session:
        await SquadHistoryWriter(session).import_dataset(seed)

    payload = json.loads(SQUAD_PATH.read_text(encoding="utf-8"))
    payload["observations"].append(
        {
            "spell_key": "future-player-galatasaray-2024",
            "revision": 2,
            "revision_kind": "details_change",
            "observed_at": "2024-09-02T12:00:00+03:00",
            "valid_from": "2024-09-01T00:00:00+03:00",
            "valid_until": None,
            "player_key": "future_player",
            "club_key": "galatasaray",
            "membership_kind": "permanent",
            "shirt_number": 77,
            "reason": "Later shirt-number observation",
        }
    )
    extended = SquadHistorySeed.model_validate(payload)

    async with TestSessionFactory() as session:
        appended = await SquadHistoryWriter(session).import_dataset(extended)

    assert appended.inserted == 1
    assert appended.conflicting == 0
    assert await _count(SquadMembershipRevisionRecord) == 7

    async with TestSessionFactory() as session:
        stale = await SquadHistoryWriter(session).import_dataset(seed)
    assert stale.inserted == 0
    assert await _count(SquadMembershipRevisionRecord) == 7

    async with TestSessionFactory() as session:
        snapshots = await SquadQuery(session).squad_at(
            "galatasaray",
            as_of=datetime.fromisoformat("2024-09-05T12:00:00+03:00"),
            knowledge_cutoff=datetime.fromisoformat("2024-09-06T12:00:00+03:00"),
        )
    future = next(item for item in snapshots if item.player_name == "Future Player")
    assert future.revision_number == 2
    assert future.shirt_number == 77


@pytest.mark.asyncio
async def test_conflicting_player_replay_rolls_back_partial_new_identity() -> None:
    await _seed_clubs()
    seed = _seed()
    async with TestSessionFactory() as session:
        await SquadHistoryWriter(session).import_dataset(seed)

    payload = seed.model_dump(mode="json")
    payload["players"].insert(
        0,
        {
            "key": "rollback_probe_player",
            "name": "Rollback Probe Player",
            "birth_date": None,
            "country_code": "TUR",
        },
    )
    for player in payload["players"]:
        if player["key"] == "late_player":
            player["name"] = "Conflicting Late Player Name"
            break
    conflicting = SquadHistorySeed.model_validate(payload)

    async with TestSessionFactory() as session:
        with pytest.raises(SquadImportConflict, match="conflicting replay for player") as exc:
            await SquadHistoryWriter(session).import_dataset(conflicting)

    assert exc.value.summary.conflicting == 1
    assert exc.value.summary.inserted >= 2
    assert await _count(Player) == 4
    probe_id = canonical_id("player", "rollback_probe_player")
    async with TestSessionFactory() as session:
        probe_entity = await session.get(CanonicalEntity, probe_id)
        probe_player = await session.get(Player, probe_id)
    assert probe_entity is None
    assert probe_player is None


@pytest.mark.asyncio
async def test_squad_at_separates_world_time_from_knowledge_time() -> None:
    await _seed_clubs()
    seed = _seed()
    async with TestSessionFactory() as session:
        await SquadHistoryWriter(session).import_dataset(seed)

    async with TestSessionFactory() as session:
        aug5_known_aug5 = await SquadQuery(session).squad_at(
            "galatasaray",
            as_of=datetime.fromisoformat("2024-08-05T12:00:00+03:00"),
            knowledge_cutoff=datetime.fromisoformat("2024-08-05T12:00:00+03:00"),
        )
        aug5_known_aug15 = await SquadQuery(session).squad_at(
            "galatasaray",
            as_of=datetime.fromisoformat("2024-08-05T12:00:00+03:00"),
            knowledge_cutoff=datetime.fromisoformat("2024-08-15T12:00:00+03:00"),
        )
        sep10_known_sep10 = await SquadQuery(session).squad_at(
            "galatasaray",
            as_of=datetime.fromisoformat("2024-09-10T12:00:00+03:00"),
            knowledge_cutoff=datetime.fromisoformat("2024-09-10T12:00:00+03:00"),
        )
        sep10_known_sep20 = await SquadQuery(session).squad_at(
            "galatasaray",
            as_of=datetime.fromisoformat("2024-09-10T12:00:00+03:00"),
            knowledge_cutoff=datetime.fromisoformat("2024-09-20T12:00:00+03:00"),
        )
        aug31 = await SquadQuery(session).squad_at(
            "galatasaray",
            as_of=datetime.fromisoformat("2024-08-31T12:00:00+03:00"),
            knowledge_cutoff=datetime.fromisoformat("2024-08-30T12:00:00+03:00"),
        )
        sep1_gala = await SquadQuery(session).squad_at(
            "galatasaray",
            as_of=datetime.fromisoformat("2024-09-01T00:00:00+03:00"),
            knowledge_cutoff=datetime.fromisoformat("2024-08-30T12:00:00+03:00"),
        )
        sep1_fener = await SquadQuery(session).squad_at(
            "fenerbahce",
            as_of=datetime.fromisoformat("2024-09-01T00:00:00+03:00"),
            knowledge_cutoff=datetime.fromisoformat("2024-08-30T12:00:00+03:00"),
        )

    assert "Late Player" not in _names(aug5_known_aug5)
    assert "Late Player" in _names(aug5_known_aug15)

    assert "Corrected Player" in _names(sep10_known_sep10)
    assert "Corrected Player" not in _names(sep10_known_sep20)

    assert "Future Player" not in _names(aug31)
    assert "Future Player" in _names(sep1_gala)

    assert "Traveler Player" not in _names(sep1_gala)
    assert "Traveler Player" in _names(sep1_fener)


@pytest.mark.asyncio
async def test_squad_query_rejects_naive_cutoffs() -> None:
    async with TestSessionFactory() as session:
        query = SquadQuery(session)
        with pytest.raises(ValueError, match="as_of must be timezone-aware"):
            await query.squad_at(
                "galatasaray",
                as_of=datetime(2024, 8, 1, 12, 0),
                knowledge_cutoff=datetime(2024, 8, 1, 12, 0, tzinfo=UTC),
            )
