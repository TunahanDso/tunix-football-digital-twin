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
from tunix_football.competition.evidence import (
    HistoricalEvidenceManifest,
    load_evidence_manifest,
)
from tunix_football.competition.loader import (
    HistoricalCompetitionLoader,
    LoadedHistoricalSeason,
)
from tunix_football.competition.persistence import (
    CanonicalHistoryWriter,
    CanonicalImportConflict,
)
from tunix_football.db.competition_models import MatchRevisionRecord
from tunix_football.db.models import Source
from tunix_football.db.session import database_url
from tunix_football.db.source_models import (
    CollectorRunRecord,
    RawSourceRecord,
    SourceConfigRecord,
)

ROOT = Path(__file__).resolve().parents[2]
SEED_PATH = ROOT / "data/competitions/tr_super_lig_2024_25.json"
FIXTURE_PATH = ROOT / "data/fixtures/tr_super_lig_2024_25_history_sample.json"
EVIDENCE_PATH = ROOT / "data/evidence/tr_super_lig_2024_25_history_sample.json"

TEST_ENGINE = create_async_engine(database_url(), poolclass=NullPool)
TestSessionFactory = async_sessionmaker(
    TEST_ENGINE,
    expire_on_commit=False,
    class_=AsyncSession,
)


@pytest_asyncio.fixture(autouse=True)
async def clean_evidence_history() -> None:
    async with TestSessionFactory() as session, session.begin():
        await session.execute(text("TRUNCATE TABLE sources, canonical_entities CASCADE"))
    yield
    async with TestSessionFactory() as session, session.begin():
        await session.execute(text("TRUNCATE TABLE sources, canonical_entities CASCADE"))


def _dataset() -> tuple[
    CompetitionSeed,
    LoadedHistoricalSeason,
    HistoricalEvidenceManifest,
]:
    loader = HistoricalCompetitionLoader()
    competition = loader.load_seed(SEED_PATH)
    history = loader.load_fixture_stream(FIXTURE_PATH, competition=competition)
    evidence = load_evidence_manifest(EVIDENCE_PATH)
    return competition, history, evidence


async def _count(model: type[object]) -> int:
    async with TestSessionFactory() as session:
        result = await session.execute(select(func.count()).select_from(model))
        return int(result.scalar_one())


@pytest.mark.asyncio
async def test_evidence_backed_import_is_traceable_end_to_end() -> None:
    competition, history, evidence = _dataset()

    async with TestSessionFactory() as session:
        summary = await CanonicalHistoryWriter(session).import_dataset(
            competition=competition,
            history=history,
            evidence=evidence,
        )

    assert summary.inserted > 0
    assert summary.conflicting == 0
    assert await _count(Source) == 1
    assert await _count(SourceConfigRecord) == 1
    assert await _count(CollectorRunRecord) == 1
    assert await _count(RawSourceRecord) == 8
    assert await _count(MatchRevisionRecord) == 9

    async with TestSessionFactory() as session:
        result = await session.execute(select(MatchRevisionRecord))
        revisions = list(result.scalars())

    assert len(revisions) == 9
    assert all(revision.source_id is not None for revision in revisions)
    assert all(revision.raw_record_id is not None for revision in revisions)

    awarded_revision_id = canonical_id(
        "match_revision",
        "2024-25-galatasaray-adana-demirspor-23:3",
    )
    async with TestSessionFactory() as session:
        revision = await session.get(MatchRevisionRecord, awarded_revision_id)
        assert revision is not None
        assert revision.source_id is not None
        assert revision.raw_record_id is not None

        source = await session.get(Source, revision.source_id)
        raw = await session.get(RawSourceRecord, revision.raw_record_id)
        assert raw is not None
        run = await session.get(CollectorRunRecord, raw.collector_run_id)

    assert source is not None
    assert source.key == "tunix_curated_tff_archive"
    assert raw.evidence_key == "pfdk-galatasaray-adana-demirspor-award-2025-02-13"
    assert raw.observed_at == datetime(2025, 2, 13, 15, 0, tzinfo=UTC)
    assert raw.fetched_at == datetime(2026, 8, 27, 12, 7, tzinfo=UTC)
    assert len(raw.content_sha256) == 64
    assert run is not None
    assert run.run_key == "super-lig-2024-25-history-sample-v1"
    assert run.records_count == 8


@pytest.mark.asyncio
async def test_identical_evidence_replay_is_idempotent() -> None:
    competition, history, evidence = _dataset()

    async with TestSessionFactory() as session:
        first = await CanonicalHistoryWriter(session).import_dataset(
            competition=competition,
            history=history,
            evidence=evidence,
        )

    counts_after_first = {
        "sources": await _count(Source),
        "configs": await _count(SourceConfigRecord),
        "runs": await _count(CollectorRunRecord),
        "raw": await _count(RawSourceRecord),
        "revisions": await _count(MatchRevisionRecord),
    }

    async with TestSessionFactory() as session:
        second = await CanonicalHistoryWriter(session).import_dataset(
            competition=competition,
            history=history,
            evidence=evidence,
        )

    assert second.inserted == 0
    assert second.existing == first.inserted
    assert second.conflicting == 0
    assert {
        "sources": await _count(Source),
        "configs": await _count(SourceConfigRecord),
        "runs": await _count(CollectorRunRecord),
        "raw": await _count(RawSourceRecord),
        "revisions": await _count(MatchRevisionRecord),
    } == counts_after_first


@pytest.mark.asyncio
async def test_legacy_canonical_revisions_can_be_enriched_with_provenance() -> None:
    competition, history, evidence = _dataset()

    async with TestSessionFactory() as session:
        await CanonicalHistoryWriter(session).import_dataset(
            competition=competition,
            history=history,
        )

    assert await _count(MatchRevisionRecord) == 9
    async with TestSessionFactory() as session:
        before_result = await session.execute(select(MatchRevisionRecord))
        before = list(before_result.scalars())
    assert all(revision.source_id is None for revision in before)
    assert all(revision.raw_record_id is None for revision in before)

    async with TestSessionFactory() as session:
        enriched = await CanonicalHistoryWriter(session).import_dataset(
            competition=competition,
            history=history,
            evidence=evidence,
        )

    assert enriched.inserted == 11
    assert enriched.conflicting == 0
    assert await _count(MatchRevisionRecord) == 9
    assert await _count(RawSourceRecord) == 8

    async with TestSessionFactory() as session:
        after_result = await session.execute(select(MatchRevisionRecord))
        after = list(after_result.scalars())
    assert all(revision.source_id is not None for revision in after)
    assert all(revision.raw_record_id is not None for revision in after)


@pytest.mark.asyncio
async def test_same_evidence_identity_with_changed_content_fails_loudly() -> None:
    competition, history, evidence = _dataset()
    async with TestSessionFactory() as session:
        await CanonicalHistoryWriter(session).import_dataset(
            competition=competition,
            history=history,
            evidence=evidence,
        )

    payload = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    payload["records"][0]["payload"]["assertion"] = "Tampered assertion"
    tampered = HistoricalEvidenceManifest.model_validate(payload)

    async with TestSessionFactory() as session:
        with pytest.raises(
            CanonicalImportConflict,
            match="conflicting replay for raw_evidence",
        ) as exc:
            await CanonicalHistoryWriter(session).import_dataset(
                competition=competition,
                history=history,
                evidence=tampered,
            )

    assert exc.value.summary.conflicting == 1
    assert await _count(Source) == 1
    assert await _count(CollectorRunRecord) == 1
    assert await _count(RawSourceRecord) == 8
    assert await _count(MatchRevisionRecord) == 9


@pytest.mark.asyncio
async def test_canonical_conflict_rolls_back_new_evidence_transaction(
    tmp_path: Path,
) -> None:
    competition, history, evidence = _dataset()
    async with TestSessionFactory() as session:
        await CanonicalHistoryWriter(session).import_dataset(
            competition=competition,
            history=history,
        )

    conflicting_payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    conflicting_payload["observations"][0]["reason"] = (
        "Conflicting historical statement used to prove rollback"
    )
    conflicting_path = tmp_path / "conflicting-history.json"
    conflicting_path.write_text(json.dumps(conflicting_payload), encoding="utf-8")
    loader = HistoricalCompetitionLoader()
    conflicting_history = loader.load_fixture_stream(
        conflicting_path,
        competition=competition,
    )

    async with TestSessionFactory() as session:
        with pytest.raises(
            CanonicalImportConflict,
            match="conflicting replay for match_revision",
        ):
            await CanonicalHistoryWriter(session).import_dataset(
                competition=competition,
                history=conflicting_history,
                evidence=evidence,
            )

    assert await _count(Source) == 0
    assert await _count(SourceConfigRecord) == 0
    assert await _count(CollectorRunRecord) == 0
    assert await _count(RawSourceRecord) == 0
    assert await _count(MatchRevisionRecord) == 9

    async with TestSessionFactory() as session:
        result = await session.execute(select(MatchRevisionRecord))
        revisions = list(result.scalars())
    assert all(revision.source_id is None for revision in revisions)
    assert all(revision.raw_record_id is None for revision in revisions)
