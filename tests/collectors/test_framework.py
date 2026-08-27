from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tunix_football.collectors.base import Collector, CollectorError
from tunix_football.collectors.demo import (
    DEMO_COLLECTOR_VERSION,
    DEMO_PARSER_VERSION,
    DEMO_SOURCE_KEY,
    DemoCollector,
)
from tunix_football.collectors.executor import CollectorExecutor
from tunix_football.collectors.registry import DuplicateSourceError, SourceRegistry
from tunix_football.collectors.types import (
    CollectionContext,
    CollectorFailureKind,
    CollectorRunStatus,
    SourceDefinition,
    SourceKind,
    SourceRecord,
    TermsStatus,
)
from tunix_football.db import source_models as _source_models  # noqa: F401
from tunix_football.db.base import Base


def demo_definition(**overrides: object) -> SourceDefinition:
    values: dict[str, object] = {
        "key": DEMO_SOURCE_KEY,
        "name": "TUNIX Synthetic Demo",
        "kind": SourceKind.SYNTHETIC,
        "parser_version": DEMO_PARSER_VERSION,
        "collector_version": DEMO_COLLECTOR_VERSION,
    }
    values.update(overrides)
    return SourceDefinition.model_validate(values)


def test_source_registry_rejects_duplicate_keys() -> None:
    registry = SourceRegistry()
    registry.register(demo_definition())

    with pytest.raises(DuplicateSourceError):
        registry.register(demo_definition())


def test_source_record_hash_is_stable_for_json_key_order() -> None:
    timestamp = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)
    first = SourceRecord.from_payload(
        source_key=DEMO_SOURCE_KEY,
        payload={"name": "A", "value": 1},
        observed_at=timestamp,
        parser_version=DEMO_PARSER_VERSION,
        collector_version=DEMO_COLLECTOR_VERSION,
    )
    second = SourceRecord.from_payload(
        source_key=DEMO_SOURCE_KEY,
        payload={"value": 1, "name": "A"},
        observed_at=timestamp,
        parser_version=DEMO_PARSER_VERSION,
        collector_version=DEMO_COLLECTOR_VERSION,
    )

    assert first.content_sha256 == second.content_sha256


@pytest.mark.asyncio
async def test_demo_collector_runs_end_to_end() -> None:
    registry = SourceRegistry()
    registry.register(demo_definition())
    result = await CollectorExecutor(registry).run(DemoCollector())

    assert result.status is CollectorRunStatus.SUCCEEDED
    assert len(result.records) == 1
    assert result.records[0].source_entity_id == "demo-club-1"
    assert result.records[0].request_context["mode"] == "synthetic"


class FailingCollector(Collector):
    source_key = DEMO_SOURCE_KEY

    async def collect(self, context: CollectionContext) -> list[SourceRecord]:
        raise CollectorError(
            f"upstream unavailable for run {context.run_id}",
            kind=CollectorFailureKind.NETWORK,
            retryable=True,
        )


@pytest.mark.asyncio
async def test_failures_are_observable_without_records() -> None:
    registry = SourceRegistry()
    registry.register(demo_definition())
    result = await CollectorExecutor(registry).run(FailingCollector())

    assert result.status is CollectorRunStatus.FAILED
    assert result.records == []
    assert result.failure is not None
    assert result.failure.kind is CollectorFailureKind.NETWORK
    assert result.failure.retryable is True


@pytest.mark.asyncio
async def test_production_collection_is_blocked_until_source_is_approved() -> None:
    registry = SourceRegistry()
    registry.register(
        demo_definition(
            terms_status=TermsStatus.UNREVIEWED,
            commercial_use_approved=False,
        )
    )
    result = await CollectorExecutor(registry, production=True).run(DemoCollector())

    assert result.status is CollectorRunStatus.BLOCKED
    assert result.failure is not None
    assert result.failure.kind is CollectorFailureKind.POLICY
    assert result.records == []


def test_ingestion_metadata_tables_are_registered() -> None:
    assert {
        "source_configs",
        "collector_runs",
        "raw_source_records",
    } <= set(Base.metadata.tables)
