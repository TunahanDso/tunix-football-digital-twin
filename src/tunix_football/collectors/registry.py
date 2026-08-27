from __future__ import annotations

from tunix_football.collectors.types import SourceDefinition


class SourceNotFoundError(KeyError):
    pass


class DuplicateSourceError(ValueError):
    pass


class SourceRegistry:
    def __init__(self) -> None:
        self._sources: dict[str, SourceDefinition] = {}

    def register(self, definition: SourceDefinition) -> None:
        if definition.key in self._sources:
            raise DuplicateSourceError(f"source already registered: {definition.key}")
        self._sources[definition.key] = definition

    def get(self, key: str) -> SourceDefinition:
        try:
            return self._sources[key]
        except KeyError as exc:
            raise SourceNotFoundError(key) from exc

    def all(self) -> tuple[SourceDefinition, ...]:
        return tuple(self._sources[key] for key in sorted(self._sources))

    def enabled(self) -> tuple[SourceDefinition, ...]:
        return tuple(source for source in self.all() if source.enabled)
