from __future__ import annotations

from abc import ABC, abstractmethod

from tunix_football.collectors.types import (
    CollectionContext,
    CollectorFailureKind,
    SourceRecord,
)


class CollectorError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        kind: CollectorFailureKind = CollectorFailureKind.UNKNOWN,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.retryable = retryable


class Collector(ABC):
    """Source adapter boundary.

    Collectors emit source-shaped evidence only. They cannot resolve canonical
    entities or mutate canonical football state; those are downstream stages.
    """

    source_key: str

    @abstractmethod
    async def collect(self, context: CollectionContext) -> list[SourceRecord]:
        raise NotImplementedError
