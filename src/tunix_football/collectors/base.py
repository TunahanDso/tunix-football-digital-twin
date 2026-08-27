from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SourceRecord(BaseModel):
    source: str
    source_entity_id: str | None = None
    observed_at: datetime
    canonical_url: str | None = None
    payload: dict[str, Any]


class Collector(ABC):
    """Adapter boundary for external football data sources.

    Collectors return source-shaped records only. They must not mutate canonical
    football state directly. Normalization, entity resolution and validation are
    separate pipeline stages.
    """

    source_name: str

    @abstractmethod
    async def collect(self) -> list[SourceRecord]:
        raise NotImplementedError
