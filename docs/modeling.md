# Modeling Strategy

## Research philosophy

No model is promoted because it sounds sophisticated. Every production model must be compared against reproducible baselines using information that would actually have been available at the historical prediction cutoff.

## Baselines

Initial benchmark ladder:

1. naive table/points baseline
2. Elo-style team ratings
3. independent Poisson goals model
4. Dixon–Coles low-score correction
5. hierarchical / state-space extensions
6. feature-rich hybrid models
7. ensemble models when justified by out-of-sample performance

## Latent team state

A central research direction is a probabilistic state-space formulation:

```text
x[t+1] = f(x[t], u[t]) + process_noise
y[t]   = g(x[t])       + observation_noise
```

Where `x` is latent football strength/state, `u` includes transfers, availability, coach changes and schedule effects, and `y` includes match and performance observations.

## Match model

Expected scoring intensity may eventually depend on:

- attacking and defensive latent states
- home advantage
- confirmed/projected lineup
- player availability
- fatigue and rest
- tactical matchup
- competition context
- weather/travel where validated

The output is a probability distribution, not a single predicted score.

## Simulation

Season and tournament probabilities will be estimated by repeated forward simulation from a dated world-state snapshot. Every simulation artifact should record:

- data cutoff
- model version
- random seed or reproducibility metadata
- scenario modifications
- number of runs
- output distributions

## Evaluation

Core metrics include:

- Log Loss
- Brier Score
- Ranked Probability Score
- calibration error / reliability curves
- likelihood for score models
- MAE only where appropriate
- championship/top-N/relegation calibration across historical snapshots

## Ablation

Feature families must earn their place. We will explicitly compare score-only, squad-aware, transfer-aware, availability-aware and richer event models to quantify marginal information value.

## Market baseline

Where legally and practically available, bookmaker/market-implied probabilities may be used as a benchmark. Beating a weak internal baseline is not sufficient evidence of a strong forecasting system.
