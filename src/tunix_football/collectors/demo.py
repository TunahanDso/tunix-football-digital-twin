from __future__ import annotations

from datetime import UTC, datetime

from tunix_football.collectors.base import Collector
from tunix_football.collectors.types import CollectionContext, SourceRecord

DEMO_SOURCE_KEY = "synthetic.demo"
DEMO_PARSER_VERSION = "1.0.0"
DEMO_COLLECTOR_VERSION = "1.0.0"


class DemoCollector(Collector):
    """Network-free collector used to prove the ingestion boundary end to end."""

    source_key = DEMO_SOURCE_KEY

    async def collect(self, context: CollectionContext) -> list[SourceRecord]:
        observed_at = datetime.now(UTC)
        payload = {
            "entity_type": "club",
            "external_id": "demo-club-1",
            "name": "TUNIX Demo FC",
            "country_code": "TUR",
        }
        return [
            SourceRecord.from_payload(
                source_key=self.source_key,
                source_entity_id="demo-club-1",
                observed_at=observed_at,
                payload=payload,
                parser_version=DEMO_PARSER_VERSION,
                collector_version=DEMO_COLLECTOR_VERSION,
                request_context={
                    "run_id": str(context.run_id),
                    "mode": "synthetic",
                },
            )
        ]
