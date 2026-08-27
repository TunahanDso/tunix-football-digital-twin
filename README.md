# TUNIX Football Digital Twin

> A temporal football intelligence platform, digital twin and probabilistic world simulation engine by TUNIX.

TUNIX Football Digital Twin aims to model football as a living, time-dependent system rather than as a collection of final scores. The long-term platform combines player intelligence, team-state estimation, event-sourced temporal data, probabilistic match models, scenario analysis, historical record queries and Monte Carlo world simulation.

## Core idea

```text
Data Sources
    ↓
Collectors → Raw Lake → Normalization → Entity Resolution → Canonical DB
                                                    ↓
                                              Football Events
                                                    ↓
Player Intelligence → Team State Engine → Match Model → World Simulator
                                                    ↓
                              Scenario / Records / Explainability / API
```

## First target

The first research and product target is the Turkish Süper Lig. We will build one league deeply before expanding the same architecture to other competitions.

## Principles

- **Temporal truth:** preserve what was true and when we learned it.
- **Event sourcing:** meaningful football changes are first-class events.
- **No single-source dependency:** source adapters are replaceable and provenance is retained.
- **Uncertainty is data:** predictions expose confidence, not only point estimates.
- **Backtest everything:** new models must beat documented baselines out of sample.
- **Explainability:** material probability changes should be attributable to causes.
- **Own the football state:** external data can inform the system, but canonical state and models are ours.

## Technology direction

- Modeling & data: Python 3.12+
- API: FastAPI
- Canonical database: PostgreSQL
- Cache: Redis
- Raw/object storage: S3-compatible storage / MinIO
- Analytics at scale: ClickHouse when justified
- High-performance services: Rust when justified
- Web product: TypeScript + Next.js

## Repository map

```text
apps/api/                  HTTP/API boundary
src/tunix_football/        core football domain and engines
docs/                      architecture and research decisions
tests/                     executable contracts and regression tests
research/                  future baselines, notebooks and experiments
infra/                     future infrastructure-specific configuration
```

## Development

Python 3.12+ and Docker are recommended.

```bash
cp .env.example .env
make infra-up
make install
make test
make api
```

API health check:

```text
GET http://localhost:8000/health
```

## Documentation

- [Architecture](docs/architecture.md)
- [Domain model](docs/domain-model.md)
- [Data strategy](docs/data-strategy.md)
- [Event sourcing & temporal truth](docs/event-sourcing.md)
- [Modeling strategy](docs/modeling.md)
- [Roadmap](docs/roadmap.md)

## Current status

**M0 — Foundation**

Architecture, temporal contracts and reproducible baselines come before large-scale data collection. The first milestone is deliberately about building the system that can safely receive years of football data before we start filling it.

## License

Proprietary. See [LICENSE.md](LICENSE.md).

---

**TUNIX — İnsan İçin Teknoloji.**
