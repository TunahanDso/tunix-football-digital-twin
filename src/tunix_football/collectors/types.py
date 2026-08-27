from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class SourceKind(StrEnum):
    FEDERATION = "federation"
    LEAGUE = "league"
    CLUB = "club"
    TRANSFER_MARKET = "transfer_market"
    STATISTICS = "statistics"
    INJURY = "injury"
    ODDS = "odds"
    WEATHER = "weather"
    NEWS = "news"
    HISTORICAL = "historical"
    SYNTHETIC = "synthetic"


class TermsStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    REVIEWED_ALLOWED = "reviewed_allowed"
    LICENSED = "licensed"
    RESTRICTED = "restricted"
    PROHIBITED = "prohibited"


class VerificationState(StrEnum):
    RAW = "raw"
    CORROBORATED = "corroborated"
    VERIFIED = "verified"
    REJECTED = "rejected"


class CollectorRunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"


class CollectorFailureKind(StrEnum):
    NETWORK = "network"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION = "authentication"
    PARSING = "parsing"
    SCHEMA = "schema"
    POLICY = "policy"
    UPSTREAM = "upstream"
    UNKNOWN = "unknown"


def canonical_json_sha256(payload: dict[str, Any]) -> str:
    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


class RequestPolicy(BaseModel):
    requests_per_minute: int = Field(default=30, ge=1)
    max_concurrency: int = Field(default=1, ge=1)
    min_interval_seconds: float = Field(default=0.0, ge=0.0)
    timeout_seconds: float = Field(default=20.0, gt=0.0)
    max_retries: int = Field(default=2, ge=0)


class SourceDefinition(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    name: str
    kind: SourceKind
    base_url: str | None = None
    reliability: float = Field(default=0.5, ge=0.0, le=1.0)
    parser_version: str
    collector_version: str
    request_policy: RequestPolicy = Field(default_factory=RequestPolicy)
    terms_status: TermsStatus = TermsStatus.UNREVIEWED
    commercial_use_approved: bool = False
    licensing_notes: str | None = None
    robots_notes: str | None = None
    enabled: bool = True

    @property
    def production_allowed(self) -> bool:
        return (
            self.enabled
            and self.commercial_use_approved
            and self.terms_status in {TermsStatus.REVIEWED_ALLOWED, TermsStatus.LICENSED}
        )


class CollectionContext(BaseModel):
    run_id: UUID = Field(default_factory=uuid4)
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    parameters: dict[str, Any] = Field(default_factory=dict)


class SourceRecord(BaseModel):
    record_id: UUID = Field(default_factory=uuid4)
    source_key: str
    source_entity_id: str | None = None
    observed_at: datetime
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    canonical_url: str | None = None
    media_type: str = "application/json"
    payload: dict[str, Any]
    content_sha256: str
    parser_version: str
    collector_version: str
    request_context: dict[str, Any] = Field(default_factory=dict)
    verification_state: VerificationState = VerificationState.RAW
    raw_object_key: str | None = None

    @classmethod
    def from_payload(
        cls,
        *,
        source_key: str,
        payload: dict[str, Any],
        observed_at: datetime,
        parser_version: str,
        collector_version: str,
        source_entity_id: str | None = None,
        canonical_url: str | None = None,
        media_type: str = "application/json",
        request_context: dict[str, Any] | None = None,
        raw_object_key: str | None = None,
    ) -> Self:
        return cls(
            source_key=source_key,
            source_entity_id=source_entity_id,
            observed_at=observed_at,
            canonical_url=canonical_url,
            media_type=media_type,
            payload=payload,
            content_sha256=canonical_json_sha256(payload),
            parser_version=parser_version,
            collector_version=collector_version,
            request_context=request_context or {},
            raw_object_key=raw_object_key,
        )

    @model_validator(mode="after")
    def validate_hash(self) -> Self:
        if len(self.content_sha256) != 64 or any(
            char not in "0123456789abcdef" for char in self.content_sha256.lower()
        ):
            raise ValueError("content_sha256 must be a 64-character SHA-256 hex digest")
        return self


class CollectorFailure(BaseModel):
    kind: CollectorFailureKind
    message: str
    retryable: bool


class CollectionRun(BaseModel):
    run_id: UUID
    source_key: str
    started_at: datetime
    finished_at: datetime
    status: CollectorRunStatus
    parser_version: str
    collector_version: str
    records: list[SourceRecord] = Field(default_factory=list)
    failure: CollectorFailure | None = None
