# Canonical Temporal Database Schema

This document records the first concrete persistence decision for TUNIX Football Digital Twin.

## Decision

PostgreSQL is the canonical truth store. Provider-specific identifiers never become domain primary keys. Every real-world football entity receives a stable TUNIX UUID in `canonical_entities`, and source-local identity is mapped through `source_entities`.

The first schema deliberately separates four concerns:

1. **Canonical identity** — who or what the entity is inside TUNIX.
2. **Football facts** — player, club, coach, competition, season and match state.
3. **Provenance and temporal knowledge** — which source said what, when it was true, and when we learned it.
4. **Model traceability** — which model version and data cutoff produced a state snapshot.

## Core graph

```text
canonical_entities
  ├── players
  ├── clubs
  ├── coaches
  └── competitions
        └── competition_seasons
              └── matches

sources
  └── source_entities ──────> canonical_entities

sources
  └── football_events ──────> canonical_entities

model_versions
  └── model_snapshots ──────> canonical_entities
```

## Canonical identity

`canonical_entities.id` is a source-independent UUID. A player remains the same canonical entity even if:

- a provider changes its numeric ID,
- a name spelling changes,
- the player transfers clubs,
- a source disappears,
- we replace one provider with another.

Provider IDs are stored only in `source_entities`.

## Bitemporal knowledge semantics

For mutable facts we distinguish real-world validity from knowledge time.

- `valid_from`: when the fact became true in the football world.
- `valid_until`: when the fact stopped being true, if known.
- `observed_at`: when TUNIX learned or recorded the fact.

This allows the system to answer two different questions:

1. **What do we believe was true at time T?**
2. **What did the model actually know at time T?**

The second question is essential for leakage-free historical backtesting.

Temporal rows enforce:

```text
valid_until IS NULL OR valid_until > valid_from
```

at the database layer.

## Sources and provenance

`sources` stores source-level metadata including:

- stable source key,
- display name,
- base URL,
- reliability prior,
- licensing/usage notes,
- latest terms review timestamp.

`source_entities` records how a provider-local entity maps into a TUNIX canonical UUID. Each mapping also stores:

- entity type,
- external ID,
- validity window,
- observation time,
- confidence,
- parser version.

This is intentionally stricter than keeping `transfermarkt_id`, `provider_x_id`, etc. directly on `players` or `clubs`.

## Football events

`football_events` is the persistence layer for event-sourced changes such as transfers, injuries, suspensions, coach changes, lineup confirmations and match completion.

Every event stores:

- immutable event UUID,
- event type,
- canonical entity UUID,
- occurrence time,
- observation time,
- validity window,
- source UUID,
- confidence,
- event schema version,
- structured JSON payload.

The payload is flexible, but the event envelope is stable and versioned.

## Competition seasons and matches

Competition rules belong to `competition_seasons`, not hard-coded application branches. This lets the same domain represent leagues whose rules change between seasons.

`matches` stores the canonical fixture/result identity and deliberately remains provider-neutral. Detailed lineups, appearances and event data will be added in later migrations rather than inflating the first migration prematurely.

## Model traceability

`model_versions` records a stable model key plus optional Git/config hashes.

`model_snapshots` stores an entity state produced by a specific model version with both:

- `as_of`: the football time the state represents,
- `data_cutoff`: the latest observation the model was allowed to use.

The explicit `data_cutoff` is a non-negotiable anti-leakage contract.

## Migration strategy

The first revision is:

```text
0001_canonical_temporal_schema
```

CI starts an empty PostgreSQL instance and executes:

```bash
alembic upgrade head
```

before running the test suite. A schema that cannot be constructed from zero is considered broken.

## What is intentionally not in v0001

The first migration does **not** attempt to model the entire football world. The following belong to later migrations:

- squad memberships and contracts,
- transfers as rich domain tables,
- injuries and suspensions as projections,
- lineups and appearances,
- detailed match events,
- stadiums and referees,
- player/team latent states,
- odds and market observations,
- scenario branches,
- simulation runs,
- raw payload metadata.

The rule is simple: establish stable identity and temporal truth first, then grow the graph without breaking historical reproducibility.
