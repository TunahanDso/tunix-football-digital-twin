# Source Registry and Collector Framework

## Purpose

TUNIX Football Digital Twin must be able to ingest many independent football data sources without allowing any one provider to define the canonical domain model.

The collector framework therefore has one rule above all others:

> **Collectors produce evidence. They do not produce truth.**

A collector may fetch a transfer page, federation fixture, official club announcement or statistical feed, but it cannot directly mutate a canonical player, club or team state. Normalization, entity resolution, validation and event creation happen downstream.

## Source definition

Every source has a `SourceDefinition` with:

- stable TUNIX source key;
- source class (`federation`, `club`, `statistics`, `transfer_market`, etc.);
- reliability prior;
- parser version;
- collector version;
- request/rate-limit policy;
- terms/licensing review status;
- commercial-use approval flag;
- robots-policy notes;
- enabled/disabled state.

The runtime `SourceRegistry` rejects duplicate source keys.

## Production policy gate

Network accessibility is not permission to use data commercially.

A source is production-collectable only when all of the following hold:

```text
enabled
AND commercial_use_approved
AND terms_status IN {reviewed_allowed, licensed}
```

The `CollectorExecutor` blocks unreviewed sources before invoking their collector in production mode. This lets research adapters exist without silently turning them into production dependencies.

## Request policy

Each source has an explicit policy envelope:

```text
requests_per_minute
max_concurrency
min_interval_seconds
timeout_seconds
max_retries
```

Actual scheduling/throttling will be implemented behind this contract. Source adapters must not invent their own hidden retry or request-rate behavior.

## Source records

Collectors emit `SourceRecord` objects containing:

- source key and optional provider entity ID;
- observation/fetch times;
- canonical source URL where applicable;
- media type;
- source-shaped payload;
- deterministic SHA-256 content hash;
- parser and collector versions;
- request context;
- verification state;
- optional immutable object-storage key.

JSON payload hashing uses sorted keys and compact separators, so semantically identical object key ordering produces the same content hash.

## Raw-first retention

Large or original source payloads belong in immutable S3/MinIO-compatible object storage. PostgreSQL stores the searchable metadata envelope in `raw_source_records`.

This separation lets us:

- preserve evidence independently of parser versions;
- reprocess old observations with improved parsers;
- prove which raw object generated a canonical fact;
- keep PostgreSQL focused on relational metadata rather than arbitrary large blobs.

## Collector runs and health

Every execution is represented as a collector run with:

- run UUID;
- source;
- start/end timestamps;
- status;
- record count;
- parser/collector versions;
- structured failure category;
- human-readable error message.

Failure taxonomy currently includes:

```text
network
rate_limit
authentication
parsing
schema
policy
upstream
unknown
```

A source failure returns evidence about the failure and zero canonical mutations. Last-write-wins behavior is explicitly forbidden at this boundary.

## Persistence tables

Migration `0002_source_ingestion_framework` adds:

```text
sources
  └── source_configs
  └── collector_runs
        └── raw_source_records
```

`source_configs` stores the operational/legal contract.

`collector_runs` gives us auditability and later health/SLA statistics.

`raw_source_records` stores provenance metadata for immutable raw evidence.

## Synthetic collector

`DemoCollector` is deliberately network-free. It proves the complete adapter contract without relying on a third-party website or introducing licensing ambiguity.

A real provider integration should not be added until:

1. its use case is documented;
2. terms/licensing have been reviewed;
3. rate limits and retry policy are explicit;
4. raw retention behavior is decided;
5. parser fixtures/tests exist;
6. it can fail without changing canonical state.

## Next boundary

After collection comes **entity resolution**.

```text
SourceRecord
    ↓
Normalization
    ↓
Entity Resolution
    ↓
Validation / Conflict Resolution
    ↓
Canonical Event
```

That boundary is intentionally outside collectors and is tracked separately in M0.3.
