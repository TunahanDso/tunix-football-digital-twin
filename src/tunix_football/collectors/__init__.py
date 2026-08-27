"""External source adapters and ingestion contracts."""

from tunix_football.collectors.base import Collector, CollectorError
from tunix_football.collectors.executor import CollectorExecutor
from tunix_football.collectors.registry import SourceRegistry
from tunix_football.collectors.types import SourceDefinition, SourceRecord

__all__ = [
    "Collector",
    "CollectorError",
    "CollectorExecutor",
    "SourceDefinition",
    "SourceRecord",
    "SourceRegistry",
]
