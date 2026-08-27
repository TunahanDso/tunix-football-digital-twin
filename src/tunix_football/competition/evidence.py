from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Self

from pydantic import BaseModel, Field, ValidationError, model_validator

from tunix_football.collectors.types import (
    SourceDefinition,
    VerificationState,
    canonical_json_sha256,
)
from tunix_football.competition.loader import LoadedHistoricalSeason


class EvidenceManifestError(ValueError):
    pass


class EvidenceObservationRef(BaseModel):
    fixture_key: str = Field(min_length=1, max_length=160)
    revision: int = Field(ge=1)

    @property
    def key(self) -> tuple[str, int]:
        return self.fixture_key, self.revision


class HistoricalEvidenceRecord(BaseModel):
    evidence_key: str = Field(pattern=r"^[a-z0-9][a-z0-9._:-]*$", max_length=256)
    observed_at: datetime
    fetched_at: datetime
    canonical_url: str | None = None
    media_type: str = Field(default="application/json", min_length=1, max_length=120)
    payload: dict[str, Any]
    source_entity_id: str | None = Field(default=None, max_length=256)
    request_context: dict[str, Any] = Field(default_factory=dict)
    verification_state: VerificationState = VerificationState.RAW
    raw_object_key: str | None = Field(default=None, max_length=1024)
    observations: list[EvidenceObservationRef] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_times(self) -> Self:
        if self.observed_at.tzinfo is None or self.fetched_at.tzinfo is None:
            raise ValueError("evidence timestamps must be timezone-aware")
        if self.fetched_at < self.observed_at:
            raise ValueError("evidence fetched_at cannot precede observed_at")
        return self

    @property
    def content_sha256(self) -> str:
        return canonical_json_sha256(self.payload)


class HistoricalEvidenceManifest(BaseModel):
    format_version: int = Field(ge=1)
    source: SourceDefinition
    run_key: str = Field(pattern=r"^[a-z0-9][a-z0-9._:-]*$", max_length=160)
    started_at: datetime
    finished_at: datetime
    records: list[HistoricalEvidenceRecord] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        if self.started_at.tzinfo is None or self.finished_at.tzinfo is None:
            raise ValueError("collector run timestamps must be timezone-aware")
        if self.finished_at < self.started_at:
            raise ValueError("collector run finished_at cannot precede started_at")

        evidence_keys = [record.evidence_key for record in self.records]
        if len(set(evidence_keys)) != len(evidence_keys):
            raise ValueError("evidence keys must be unique within a manifest")

        refs = [ref.key for record in self.records for ref in record.observations]
        if len(set(refs)) != len(refs):
            raise ValueError("each fixture revision must have one primary evidence record")

        for record in self.records:
            if not self.started_at <= record.fetched_at <= self.finished_at:
                raise ValueError(
                    f"evidence {record.evidence_key} fetched_at is outside collector run"
                )
        return self

    def bindings_for(
        self,
        history: LoadedHistoricalSeason,
    ) -> dict[tuple[str, int], HistoricalEvidenceRecord]:
        expected = {
            (timeline.fixture_key, observation.revision)
            for timeline in history.fixtures
            for observation in timeline.observations
        }
        bindings = {
            ref.key: record
            for record in self.records
            for ref in record.observations
        }
        actual = set(bindings)
        missing = expected - actual
        unknown = actual - expected
        if missing or unknown:
            details: list[str] = []
            if missing:
                details.append(f"missing evidence for {sorted(missing)}")
            if unknown:
                details.append(f"unknown observation refs {sorted(unknown)}")
            raise EvidenceManifestError("; ".join(details))
        return bindings


def load_evidence_manifest(path: str | Path) -> HistoricalEvidenceManifest:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceManifestError(f"cannot load evidence manifest from {path}: {exc}") from exc

    try:
        return HistoricalEvidenceManifest.model_validate(payload)
    except ValidationError as exc:
        raise EvidenceManifestError(f"invalid evidence manifest: {exc}") from exc
