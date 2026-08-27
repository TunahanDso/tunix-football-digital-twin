from __future__ import annotations

from datetime import UTC, datetime

from tunix_football.collectors.base import Collector, CollectorError
from tunix_football.collectors.registry import SourceRegistry
from tunix_football.collectors.types import (
    CollectionContext,
    CollectionRun,
    CollectorFailure,
    CollectorFailureKind,
    CollectorRunStatus,
)


class CollectorExecutor:
    """Runs collectors without giving them access to canonical football state."""

    def __init__(self, registry: SourceRegistry, *, production: bool = False) -> None:
        self._registry = registry
        self._production = production

    async def run(
        self,
        collector: Collector,
        context: CollectionContext | None = None,
    ) -> CollectionRun:
        definition = self._registry.get(collector.source_key)
        run_context = context or CollectionContext()
        started_at = datetime.now(UTC)

        if self._production and not definition.production_allowed:
            return CollectionRun(
                run_id=run_context.run_id,
                source_key=definition.key,
                started_at=started_at,
                finished_at=datetime.now(UTC),
                status=CollectorRunStatus.BLOCKED,
                parser_version=definition.parser_version,
                collector_version=definition.collector_version,
                failure=CollectorFailure(
                    kind=CollectorFailureKind.POLICY,
                    message="source is not approved for production collection",
                    retryable=False,
                ),
            )

        try:
            records = await collector.collect(run_context)
            for record in records:
                if record.source_key != definition.key:
                    raise CollectorError(
                        "collector emitted a record for a different source",
                        kind=CollectorFailureKind.SCHEMA,
                    )
                if record.parser_version != definition.parser_version:
                    raise CollectorError(
                        "record parser_version differs from source definition",
                        kind=CollectorFailureKind.SCHEMA,
                    )
                if record.collector_version != definition.collector_version:
                    raise CollectorError(
                        "record collector_version differs from source definition",
                        kind=CollectorFailureKind.SCHEMA,
                    )
        except CollectorError as exc:
            return CollectionRun(
                run_id=run_context.run_id,
                source_key=definition.key,
                started_at=started_at,
                finished_at=datetime.now(UTC),
                status=CollectorRunStatus.FAILED,
                parser_version=definition.parser_version,
                collector_version=definition.collector_version,
                failure=CollectorFailure(
                    kind=exc.kind,
                    message=str(exc),
                    retryable=exc.retryable,
                ),
            )
        except Exception as exc:  # noqa: BLE001 - boundary converts unknown source failures
            return CollectionRun(
                run_id=run_context.run_id,
                source_key=definition.key,
                started_at=started_at,
                finished_at=datetime.now(UTC),
                status=CollectorRunStatus.FAILED,
                parser_version=definition.parser_version,
                collector_version=definition.collector_version,
                failure=CollectorFailure(
                    kind=CollectorFailureKind.UNKNOWN,
                    message=str(exc),
                    retryable=False,
                ),
            )

        return CollectionRun(
            run_id=run_context.run_id,
            source_key=definition.key,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            status=CollectorRunStatus.SUCCEEDED,
            parser_version=definition.parser_version,
            collector_version=definition.collector_version,
            records=records,
        )
