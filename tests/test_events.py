from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from tunix_football.events.base import FootballEvent, FootballEventType


def test_event_accepts_valid_temporal_window() -> None:
    start = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
    event = FootballEvent(
        event_type=FootballEventType.PLAYER_TRANSFERRED,
        entity_id=uuid4(),
        occurred_at=start,
        observed_at=start + timedelta(minutes=3),
        valid_from=start,
        source_id="official-club",
        confidence=1.0,
        payload={"from_club_id": "a", "to_club_id": "b"},
    )

    assert event.event_type is FootballEventType.PLAYER_TRANSFERRED
    assert event.observed_at > event.occurred_at


def test_event_rejects_invalid_validity_window() -> None:
    start = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="valid_until"):
        FootballEvent(
            event_type=FootballEventType.PLAYER_INJURED,
            entity_id=uuid4(),
            occurred_at=start,
            valid_from=start,
            valid_until=start - timedelta(seconds=1),
            source_id="official-club",
            confidence=0.95,
        )
