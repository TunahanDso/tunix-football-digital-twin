from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tunix_football.canonical_ids import canonical_id
from tunix_football.collectors.types import CollectorRunStatus
from tunix_football.competition.contracts import CompetitionSeed, SeasonSeed
from tunix_football.competition.evidence import HistoricalEvidenceManifest
from tunix_football.competition.loader import LoadedHistoricalSeason
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
    Source,
)
from tunix_football.db.source_models import (
    CollectorRunRecord,
    RawSourceRecord,
    SourceConfigRecord,
)

EvidenceBindingMap = dict[tuple[str, int], tuple[UUID, UUID]]


@dataclass(slots=True)
class ImportSummary:
    inserted: int = 0
    existing: int = 0
    conflicting: int = 0

    def mark(self, *, existed: bool) -> None:
        if existed:
            self.existing += 1
        else:
            self.inserted += 1

    def mark_conflict(self) -> None:
        self.conflicting += 1


class CanonicalImportConflict(ValueError):
    """Raised when a deterministic logical key resolves to conflicting truth."""

    def __init__(self, message: str, *, summary: ImportSummary) -> None:
        super().__init__(message)
        self.summary = summary


class CanonicalHistoryWriter:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def import_dataset(
        self,
        *,
        competition: CompetitionSeed,
        history: LoadedHistoricalSeason,
        evidence: HistoricalEvidenceManifest | None = None,
    ) -> ImportSummary:
        summary = ImportSummary()
        if history.competition.key != competition.key:
            summary.mark_conflict()
            raise CanonicalImportConflict(
                "history competition does not match seed",
                summary=summary,
            )

        evidence_records = evidence.bindings_for(history) if evidence is not None else None

        async with self._session.begin():
            await self._persist_competitions(competition, summary)
            await self._persist_clubs(competition, summary)
            await self._session.flush()
            for season in competition.seasons:
                await self._persist_season(competition, season, summary)
            await self._session.flush()

            evidence_bindings: EvidenceBindingMap = {}
            if evidence is not None and evidence_records is not None:
                evidence_bindings = await self._persist_evidence(
                    evidence,
                    evidence_records,
                    summary,
                )

            await self._persist_history(
                history,
                summary,
                evidence_bindings=evidence_bindings,
            )
        return summary

    async def _persist_competitions(
        self,
        seed: CompetitionSeed,
        summary: ImportSummary,
    ) -> None:
        rows = [
            (
                seed.key,
                seed.name,
                seed.country_code,
                seed.competition_type.value,
            ),
            *[
                (
                    item.key,
                    item.name,
                    item.country_code,
                    item.competition_type.value,
                )
                for item in seed.related_competitions
            ],
        ]
        for key, name, country_code, competition_type in rows:
            entity_id = canonical_id("competition", key)
            await self._persist_entity(entity_id, "competition", summary)
            existing = await self._session.get(Competition, entity_id)
            expected = {
                "canonical_name": name,
                "country_code": country_code,
                "competition_type": competition_type,
            }
            if existing is None:
                self._session.add(
                    Competition(
                        entity_id=entity_id,
                        canonical_name=name,
                        country_code=country_code,
                        competition_type=competition_type,
                    )
                )
                summary.mark(existed=False)
            else:
                self._assert_fields(
                    f"competition:{key}",
                    existing,
                    expected,
                    summary,
                )
                summary.mark(existed=True)

    async def _persist_clubs(
        self,
        seed: CompetitionSeed,
        summary: ImportSummary,
    ) -> None:
        for club in seed.clubs:
            entity_id = canonical_id("club", club.key)
            await self._persist_entity(entity_id, "club", summary)
            existing = await self._session.get(Club, entity_id)
            expected = {
                "canonical_name": club.name,
                "country_code": club.country_code,
            }
            if existing is None:
                self._session.add(
                    Club(
                        entity_id=entity_id,
                        canonical_name=club.name,
                        short_name=None,
                        country_code=club.country_code,
                    )
                )
                summary.mark(existed=False)
            else:
                self._assert_fields(f"club:{club.key}", existing, expected, summary)
                summary.mark(existed=True)

    async def _persist_entity(
        self,
        entity_id: UUID,
        entity_type: str,
        summary: ImportSummary,
    ) -> None:
        existing = await self._session.get(CanonicalEntity, entity_id)
        if existing is None:
            self._session.add(
                CanonicalEntity(
                    id=entity_id,
                    entity_type=entity_type,
                    retired_at=None,
                )
            )
            summary.mark(existed=False)
            return
        self._assert_fields(
            f"canonical_entity:{entity_id}",
            existing,
            {"entity_type": entity_type, "retired_at": None},
            summary,
        )
        summary.mark(existed=True)

    async def _persist_season(
        self,
        competition: CompetitionSeed,
        season: SeasonSeed,
        summary: ImportSummary,
    ) -> None:
        competition_id = canonical_id("competition", competition.key)
        season_id = canonical_id("season", f"{competition.key}:{season.key}")
        rules_json = season.rules.model_dump(mode="json")
        existing = await self._session.get(CompetitionSeason, season_id)
        expected_identity = {
            "competition_id": competition_id,
            "season_key": season.key,
            "starts_on": season.starts_on,
            "ends_on": season.ends_on,
        }
        if existing is None:
            self._session.add(
                CompetitionSeason(
                    id=season_id,
                    competition_id=competition_id,
                    season_key=season.key,
                    starts_on=season.starts_on,
                    ends_on=season.ends_on,
                    rules=rules_json,
                )
            )
            summary.mark(existed=False)
        else:
            self._assert_fields(
                f"season:{competition.key}:{season.key}",
                existing,
                expected_identity,
                summary,
            )
            existing.rules = rules_json
            summary.mark(existed=True)

        rule_id = canonical_id(
            "season_rule",
            f"{competition.key}:{season.key}:{season.rules.version}",
        )
        rule = await self._session.get(SeasonRuleVersionRecord, rule_id)
        rule_expected = {
            "competition_season_id": season_id,
            "version": season.rules.version,
            "valid_from": season.rules_valid_from.astimezone(UTC),
            "observed_at": season.rules_observed_at.astimezone(UTC),
            "supersedes_id": None,
            "rules": rules_json,
        }
        if rule is None:
            self._session.add(
                SeasonRuleVersionRecord(
                    id=rule_id,
                    competition_season_id=season_id,
                    version=season.rules.version,
                    valid_from=season.rules_valid_from.astimezone(UTC),
                    observed_at=season.rules_observed_at.astimezone(UTC),
                    supersedes_id=None,
                    rules=rules_json,
                )
            )
            summary.mark(existed=False)
        else:
            self._assert_fields(
                f"season_rule:{competition.key}:{season.key}:{season.rules.version}",
                rule,
                rule_expected,
                summary,
            )
            summary.mark(existed=True)

        for participant in season.participants:
            participation_id = canonical_id(
                "season_participation",
                f"{competition.key}:{season.key}:{participant.club_key}",
            )
            club_id = canonical_id("club", participant.club_key)
            from_id = self._optional_competition_id(participant.from_competition_key)
            to_id = self._optional_competition_id(participant.to_competition_key)
            existing_participation = await self._session.get(
                SeasonClubParticipationRecord,
                participation_id,
            )
            expected = {
                "competition_season_id": season_id,
                "club_id": club_id,
                "entry_type": participant.entry.value,
                "exit_type": participant.exit.value,
                "from_competition_id": from_id,
                "to_competition_id": to_id,
            }
            if existing_participation is None:
                self._session.add(
                    SeasonClubParticipationRecord(
                        id=participation_id,
                        competition_season_id=season_id,
                        club_id=club_id,
                        entry_type=participant.entry.value,
                        exit_type=participant.exit.value,
                        from_competition_id=from_id,
                        to_competition_id=to_id,
                    )
                )
                summary.mark(existed=False)
            else:
                self._assert_fields(
                    f"participation:{competition.key}:{season.key}:{participant.club_key}",
                    existing_participation,
                    expected,
                    summary,
                )
                summary.mark(existed=True)

    async def _persist_evidence(
        self,
        manifest: HistoricalEvidenceManifest,
        records_by_observation: dict[tuple[str, int], object],
        summary: ImportSummary,
    ) -> EvidenceBindingMap:
        source_id = canonical_id("source", manifest.source.key)
        run_id = canonical_id(
            "collector_run",
            f"{manifest.source.key}:{manifest.run_key}",
        )
        await self._persist_source(source_id, manifest, summary)
        await self._session.flush()
        await self._persist_source_config(source_id, manifest, summary)
        await self._persist_collector_run(source_id, run_id, manifest, summary)
        await self._session.flush()

        record_ids: dict[str, UUID] = {}
        for record in manifest.records:
            record_id = canonical_id(
                "raw_evidence",
                f"{manifest.source.key}:{record.evidence_key}",
            )
            await self._persist_raw_record(
                source_id,
                run_id,
                record_id,
                manifest,
                record,
                summary,
            )
            record_ids[record.evidence_key] = record_id

        return {
            observation_key: (
                source_id,
                record_ids[record.evidence_key],
            )
            for observation_key, record in records_by_observation.items()
        }

    async def _persist_source(
        self,
        source_id: UUID,
        manifest: HistoricalEvidenceManifest,
        summary: ImportSummary,
    ) -> None:
        source = manifest.source
        existing = await self._session.get(Source, source_id)
        expected = {
            "key": source.key,
            "name": source.name,
            "base_url": source.base_url,
            "reliability": Decimal(str(source.reliability)),
            "licensing_notes": source.licensing_notes,
        }
        if existing is None:
            self._session.add(
                Source(
                    id=source_id,
                    key=source.key,
                    name=source.name,
                    base_url=source.base_url,
                    reliability=Decimal(str(source.reliability)),
                    licensing_notes=source.licensing_notes,
                    terms_reviewed_at=None,
                )
            )
            summary.mark(existed=False)
            return
        self._assert_fields(f"source:{source.key}", existing, expected, summary)
        summary.mark(existed=True)

    async def _persist_source_config(
        self,
        source_id: UUID,
        manifest: HistoricalEvidenceManifest,
        summary: ImportSummary,
    ) -> None:
        source = manifest.source
        existing = await self._session.get(SourceConfigRecord, source_id)
        expected = {
            "source_kind": source.kind.value,
            "parser_version": source.parser_version,
            "collector_version": source.collector_version,
            "request_policy": source.request_policy.model_dump(mode="json"),
            "terms_status": source.terms_status.value,
            "commercial_use_approved": source.commercial_use_approved,
            "robots_notes": source.robots_notes,
            "enabled": source.enabled,
        }
        if existing is None:
            self._session.add(
                SourceConfigRecord(
                    source_id=source_id,
                    source_kind=source.kind.value,
                    parser_version=source.parser_version,
                    collector_version=source.collector_version,
                    request_policy=source.request_policy.model_dump(mode="json"),
                    terms_status=source.terms_status.value,
                    commercial_use_approved=source.commercial_use_approved,
                    robots_notes=source.robots_notes,
                    enabled=source.enabled,
                )
            )
            summary.mark(existed=False)
            return
        self._assert_fields(
            f"source_config:{source.key}",
            existing,
            expected,
            summary,
        )
        summary.mark(existed=True)

    async def _persist_collector_run(
        self,
        source_id: UUID,
        run_id: UUID,
        manifest: HistoricalEvidenceManifest,
        summary: ImportSummary,
    ) -> None:
        existing = await self._session.get(CollectorRunRecord, run_id)
        expected = {
            "source_id": source_id,
            "started_at": manifest.started_at.astimezone(UTC),
            "finished_at": manifest.finished_at.astimezone(UTC),
            "status": CollectorRunStatus.SUCCEEDED.value,
            "records_count": len(manifest.records),
            "parser_version": manifest.source.parser_version,
            "collector_version": manifest.source.collector_version,
            "failure_kind": None,
            "error_message": None,
        }
        if existing is None:
            self._session.add(
                CollectorRunRecord(
                    run_id=run_id,
                    source_id=source_id,
                    started_at=manifest.started_at.astimezone(UTC),
                    finished_at=manifest.finished_at.astimezone(UTC),
                    status=CollectorRunStatus.SUCCEEDED.value,
                    records_count=len(manifest.records),
                    parser_version=manifest.source.parser_version,
                    collector_version=manifest.source.collector_version,
                    failure_kind=None,
                    error_message=None,
                )
            )
            summary.mark(existed=False)
            return
        self._assert_fields(
            f"collector_run:{manifest.source.key}:{manifest.run_key}",
            existing,
            expected,
            summary,
        )
        summary.mark(existed=True)

    async def _persist_raw_record(
        self,
        source_id: UUID,
        run_id: UUID,
        record_id: UUID,
        manifest: HistoricalEvidenceManifest,
        record: Any,
        summary: ImportSummary,
    ) -> None:
        existing = await self._session.get(RawSourceRecord, record_id)
        expected = {
            "source_id": source_id,
            "collector_run_id": run_id,
            "evidence_key": record.evidence_key,
            "source_entity_id": record.source_entity_id,
            "observed_at": record.observed_at.astimezone(UTC),
            "fetched_at": record.fetched_at.astimezone(UTC),
            "canonical_url": record.canonical_url,
            "media_type": record.media_type,
            "content_sha256": record.content_sha256,
            "raw_object_key": record.raw_object_key,
            "parser_version": manifest.source.parser_version,
            "collector_version": manifest.source.collector_version,
            "request_context": record.request_context,
            "verification_state": record.verification_state.value,
        }
        if existing is None:
            self._session.add(
                RawSourceRecord(
                    record_id=record_id,
                    source_id=source_id,
                    collector_run_id=run_id,
                    evidence_key=record.evidence_key,
                    source_entity_id=record.source_entity_id,
                    observed_at=record.observed_at.astimezone(UTC),
                    fetched_at=record.fetched_at.astimezone(UTC),
                    canonical_url=record.canonical_url,
                    media_type=record.media_type,
                    content_sha256=record.content_sha256,
                    raw_object_key=record.raw_object_key,
                    parser_version=manifest.source.parser_version,
                    collector_version=manifest.source.collector_version,
                    request_context=record.request_context,
                    verification_state=record.verification_state.value,
                )
            )
            summary.mark(existed=False)
            return
        self._assert_fields(
            f"raw_evidence:{manifest.source.key}:{record.evidence_key}",
            existing,
            expected,
            summary,
        )
        summary.mark(existed=True)

    async def _persist_history(
        self,
        history: LoadedHistoricalSeason,
        summary: ImportSummary,
        *,
        evidence_bindings: EvidenceBindingMap,
    ) -> None:
        season_id = canonical_id(
            "season",
            f"{history.competition.key}:{history.season.key}",
        )
        for timeline in history.fixtures:
            match_id = canonical_id("match", timeline.fixture_key)
            latest = timeline.latest
            existing_match = await self._session.get(Match, match_id)
            immutable = {
                "competition_season_id": season_id,
                "home_club_id": canonical_id("club", latest.home_club_key),
                "away_club_id": canonical_id("club", latest.away_club_key),
            }
            if existing_match is None:
                self._session.add(
                    Match(
                        id=match_id,
                        competition_season_id=season_id,
                        home_club_id=canonical_id("club", latest.home_club_key),
                        away_club_id=canonical_id("club", latest.away_club_key),
                        kickoff_at=latest.kickoff_at_utc,
                        status=latest.status.value,
                        home_score=latest.home_score,
                        away_score=latest.away_score,
                    )
                )
                summary.mark(existed=False)
                await self._session.flush()
            else:
                self._assert_fields(
                    f"match:{timeline.fixture_key}",
                    existing_match,
                    immutable,
                    summary,
                )
                summary.mark(existed=True)

            for observation in timeline.observations:
                revision_id = canonical_id(
                    "match_revision",
                    f"{timeline.fixture_key}:{observation.revision}",
                )
                binding = evidence_bindings.get(
                    (timeline.fixture_key, observation.revision)
                )
                source_id = binding[0] if binding is not None else None
                raw_record_id = binding[1] if binding is not None else None
                existing_revision = await self._session.get(
                    MatchRevisionRecord,
                    revision_id,
                )
                expected_revision = {
                    "match_id": match_id,
                    "revision_number": observation.revision,
                    "revision_kind": observation.revision_kind.value,
                    "observed_at": observation.observed_at_utc,
                    "kickoff_at": observation.kickoff_at_utc,
                    "status": observation.status.value,
                    "home_score": observation.home_score,
                    "away_score": observation.away_score,
                    "reason": observation.reason,
                }
                if existing_revision is None:
                    self._session.add(
                        MatchRevisionRecord(
                            id=revision_id,
                            match_id=match_id,
                            revision_number=observation.revision,
                            revision_kind=observation.revision_kind.value,
                            observed_at=observation.observed_at_utc,
                            kickoff_at=observation.kickoff_at_utc,
                            status=observation.status.value,
                            home_score=observation.home_score,
                            away_score=observation.away_score,
                            source_id=source_id,
                            raw_record_id=raw_record_id,
                            reason=observation.reason,
                        )
                    )
                    summary.mark(existed=False)
                else:
                    self._assert_fields(
                        f"match_revision:{timeline.fixture_key}:{observation.revision}",
                        existing_revision,
                        expected_revision,
                        summary,
                    )
                    self._bind_existing_revision_evidence(
                        existing_revision,
                        source_id,
                        raw_record_id,
                        timeline.fixture_key,
                        observation.revision,
                        summary,
                    )
                    summary.mark(existed=True)

            await self._session.flush()
            result = await self._session.execute(
                select(func.max(MatchRevisionRecord.revision_number)).where(
                    MatchRevisionRecord.match_id == match_id
                )
            )
            stored_latest_revision = result.scalar_one()
            if stored_latest_revision == latest.revision:
                match = await self._session.get(Match, match_id)
                if match is None:
                    raise AssertionError("match disappeared during import")
                match.kickoff_at = latest.kickoff_at_utc
                match.status = latest.status.value
                match.home_score = latest.home_score
                match.away_score = latest.away_score

    def _bind_existing_revision_evidence(
        self,
        revision: MatchRevisionRecord,
        source_id: UUID | None,
        raw_record_id: UUID | None,
        fixture_key: str,
        revision_number: int,
        summary: ImportSummary,
    ) -> None:
        if source_id is None and raw_record_id is None:
            return
        if source_id is None or raw_record_id is None:
            summary.mark_conflict()
            raise CanonicalImportConflict(
                "evidence binding must contain both source_id and raw_record_id",
                summary=summary,
            )
        if revision.source_id is None and revision.raw_record_id is None:
            revision.source_id = source_id
            revision.raw_record_id = raw_record_id
            return
        if revision.source_id != source_id or revision.raw_record_id != raw_record_id:
            summary.mark_conflict()
            raise CanonicalImportConflict(
                "conflicting evidence binding for "
                f"match_revision:{fixture_key}:{revision_number}",
                summary=summary,
            )

    @staticmethod
    def _optional_competition_id(key: str | None) -> UUID | None:
        if key is None:
            return None
        return canonical_id("competition", key)

    @staticmethod
    def _assert_fields(
        label: str,
        record: object,
        expected: dict[str, Any],
        summary: ImportSummary,
    ) -> None:
        conflicts = {
            field: (getattr(record, field), value)
            for field, value in expected.items()
            if getattr(record, field) != value
        }
        if conflicts:
            summary.mark_conflict()
            raise CanonicalImportConflict(
                f"conflicting replay for {label}: {conflicts}",
                summary=summary,
            )
