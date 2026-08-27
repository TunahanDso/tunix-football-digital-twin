# Roadmap

## M0 — Foundation

- establish repository and engineering standards
- define temporal/event contracts
- define canonical identity strategy
- define PostgreSQL schema direction
- create source-adapter boundary
- add reproducible local infrastructure
- implement first baseline research harness

## M1 — Süper Lig Canonical Data Core

- competitions, seasons, clubs, players and matches
- canonical IDs and source mappings
- source provenance and raw retention
- historical fixture/result ingestion
- temporal squad membership
- migration framework and database tests

## M2 — Baseline Forecasting

- Elo baseline
- Poisson goals baseline
- Dixon–Coles baseline
- rolling historical backtests
- Log Loss, Brier Score and calibration reports
- model snapshot/version registry

## M3 — Player & Squad Intelligence

- player participation/minutes features
- role and position representation
- squad depth model
- transfer-event impact prior
- injury/suspension availability state
- ablation testing against score-only baselines

## M4 — Living Team State

- probabilistic/state-space team representation
- attack/defence and richer latent dimensions
- lineup-aware forecasts
- fatigue/rest effects
- coach-change priors
- uncertainty propagation

## M5 — Football World Simulator

- season Monte Carlo engine
- title/top-N/relegation distributions
- cup/tournament simulation
- deterministic reproducibility controls
- scenario forks and counterfactual worlds

## M6 — Product Layer

- Match Center
- League Intelligence
- Club Intelligence
- Player Intelligence
- Transfer Lab
- Scenario Lab
- Prediction History
- Explainability views
- subscriptions and account layer

## M7 — Records & Query Engine

- historical record DSL
- derived record discovery
- temporal football queries
- natural-language-to-structured-query layer

## Expansion

Only after the Süper Lig pipeline, models and validation framework are stable should the platform expand to additional leagues and UEFA competitions.
