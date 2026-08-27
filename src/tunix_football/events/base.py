from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class FootballEventType(StrEnum):
    PLAYER_TRANSFERRED = "player.transferred"
    PLAYER_INJURED = "player.injured"
    PLAYER_RETURNED = "player.returned"
    PLAYER_SUSPENDED = "player.suspended"
    COACH_CHANGED = "coach.changed"
    LINEUP_CONFIRMED = "lineup.confirmed"
    MATCH_FINISHED = "match.finished"


class FootballEvent(BaseModel):
    """Immutable domain event with both real-world and knowledge-time semantics."""

    event_id: UUID = Field(default_factory=uuid4)
    event_type: FootballEventType
    entity_id: UUID
    occurred_at: datetime
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    valid_from: datetime
    valid_until: datetime | None = None
    source_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_temporal_window(self) -> FootballEvent:
        if self.valid_until is not None and self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be later than valid_from")
        return self
