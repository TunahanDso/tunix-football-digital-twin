from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class EntityType(StrEnum):
    PLAYER = "player"
    CLUB = "club"
    COACH = "coach"
    COMPETITION = "competition"


class ResolutionStatus(StrEnum):
    MATCHED = "matched"
    AMBIGUOUS = "ambiguous"
    UNMATCHED = "unmatched"


class ResolutionMethod(StrEnum):
    EXACT = "exact"
    FUZZY = "fuzzy"
    ATTRIBUTE = "attribute"
    MANUAL = "manual"
    NONE = "none"


class AliasRecord(BaseModel):
    canonical_entity_id: UUID
    entity_type: EntityType
    alias: str
    valid_from: datetime | None = None
    valid_until: datetime | None = None

    @model_validator(mode="after")
    def validate_window(self) -> AliasRecord:
        if (
            self.valid_from is not None
            and self.valid_until is not None
            and self.valid_until <= self.valid_from
        ):
            raise ValueError("valid_until must be later than valid_from")
        return self

    def is_valid_at(self, instant: datetime) -> bool:
        if self.valid_from is not None and instant < self.valid_from:
            return False
        return self.valid_until is None or instant < self.valid_until


class CanonicalCandidate(BaseModel):
    canonical_entity_id: UUID = Field(default_factory=uuid4)
    entity_type: EntityType
    canonical_name: str
    aliases: list[AliasRecord] = Field(default_factory=list)
    birth_date: date | None = None
    country_code: str | None = None


class ResolutionRequest(BaseModel):
    source_key: str
    source_entity_id: str | None = None
    entity_type: EntityType
    name: str
    as_of: datetime
    birth_date: date | None = None
    country_code: str | None = None


class CandidateScore(BaseModel):
    canonical_entity_id: UUID
    score: float = Field(ge=0.0, le=1.0)
    name_score: float = Field(ge=0.0, le=1.0)
    reasons: tuple[str, ...] = ()


class ResolutionResult(BaseModel):
    status: ResolutionStatus
    method: ResolutionMethod
    request: ResolutionRequest
    resolved_entity_id: UUID | None = None
    candidates: list[CandidateScore] = Field(default_factory=list)
    explanation: str


class ReviewCase(BaseModel):
    case_id: UUID = Field(default_factory=uuid4)
    request: ResolutionRequest
    candidates: list[CandidateScore]
    reason: str
