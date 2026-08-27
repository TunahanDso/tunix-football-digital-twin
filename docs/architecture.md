# Architecture

## Goal

TUNIX Football Digital Twin models football as a temporal, event-driven world state. The system should be able to answer both **what is true now?** and **what did we know at a past point in time?**, then simulate plausible futures from either state.

## High-level flow

```text
External Sources
   ↓
Collectors
   ↓
Raw Data Lake
   ↓
Normalization
   ↓
Entity Resolution
   ↓
Validation + Provenance
   ↓
Canonical PostgreSQL Store
   ↓
Football Event Stream
   ↓
Feature Store / State Estimation
   ↓
Player Intelligence
   ↓
Team State Engine
   ↓
Match Probability Models
   ↓
World Simulation Engine
   ↓
Scenario / Records / Explainability / API
```

## Architectural principles

### 1. Modular monolith first
We begin with one deployable backend and strong module boundaries. Microservices are introduced only when scale, ownership or isolation justifies them.

### 2. Event-driven domain
Transfers, injuries, suspensions, coach changes, lineups and match outcomes are modeled as explicit events. Derived state can be rebuilt from the event history.

### 3. Bitemporal thinking
We distinguish:
- **valid time**: when a fact is/was true in the football world;
- **observed time**: when our system learned the fact.

This is required for honest historical backtesting without future information leakage.

### 4. Source adapters are replaceable
Collectors never write canonical state directly. They emit raw source records. Normalization and entity resolution sit between source data and domain truth.

### 5. Model versioning is mandatory
Every state estimate, prediction and simulation result must be attributable to a model version, feature version and data cutoff.

## Initial infrastructure

- PostgreSQL: canonical relational/temporal truth
- Redis: cache and ephemeral coordination
- MinIO/S3: immutable raw payloads and large artifacts
- FastAPI: application/API boundary
- Python: modeling and data pipeline language

ClickHouse, Redpanda/Kafka and Rust services are intentionally deferred until workload evidence requires them.
