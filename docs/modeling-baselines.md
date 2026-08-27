# Forecasting Baselines and Backtest Protocol

## Why baselines come before richer football features

TUNIX should earn complexity. Player availability, transfers, tactical state, travel, weather and market signals are only useful if their incremental predictive value can be measured against simple, reproducible models.

M0.4 therefore establishes three deliberately understandable baselines:

1. an Elo-style team-strength model;
2. an independent Poisson goals model;
3. a Poisson model with a Dixon–Coles low-score correction.

These are benchmark models, not the final digital twin.

## Information time is a hard boundary

Every prediction has a `prediction_cutoff`. For a T-24h experiment, the cutoff is exactly 24 hours before kickoff. Training data may only contain match results whose `result_observed_at` is at or before that cutoff.

The walk-forward harness refits a fresh model for every target match. This is slower than reusing a mutable fitted object, but it makes state leakage much harder to hide and gives every prediction an auditable training boundary.

Each output records both:

- `prediction_cutoff`: when the forecast is considered to have been made;
- `data_cutoff`: the newest training observation actually available to that forecast.

The database enforces `data_cutoff <= prediction_cutoff`.

## Market benchmarking must use the same clock

A closing bookmaker price contains information that may not have existed 24 hours earlier: confirmed lineups, injuries, suspensions, late transfers, weather, market order flow and breaking news.

Therefore a T-24h model is compared to the latest market snapshot available at or before T-24h. A T-5m model is compared to a market snapshot available at or before T-5m.

Closing odds may still be reported as a separate upper-bound reference, but they must not be presented as an apples-to-apples opponent for an earlier forecast.

`MarketSnapshot` accepts probabilities rather than raw decimal odds. Bookmaker margin/overround must be removed upstream and the normalization method should be retained in source provenance. The harness rejects probability vectors that do not sum to one.

## Metrics

The common evaluation interface reports:

- multiclass Log Loss;
- multiclass Brier Score;
- Ranked Probability Score for 1X2;
- scoreline log loss where a model exposes a score distribution;
- class-wise calibration bins and Expected Calibration Error;
- paired model-minus-market RPS delta with a deterministic bootstrap 95% interval.

For every proper score, lower is better. A positive `model - market` RPS delta means the model was worse than the time-aligned market on the paired match set.

ECE is never sufficient by itself. Calibration should later be sliced by outcome class, lead time, season, competition and regime, and evaluated together with sharpness/resolution.

## Reproducibility

A backtest report carries:

- model key;
- model configuration;
- configuration SHA-256;
- deterministic historical data snapshot SHA-256;
- random seed;
- lead time;
- per-match prediction and data cutoffs.

Persistent runs additionally reference a `model_version_id`, so a metric cannot be detached from the code/model lineage that created it.

## Baseline limitations

The current independent Poisson baseline estimates venue-specific attack and defense strength with shrinkage toward league scoring means. Dixon–Coles adds the classic low-score dependency correction using a configurable `rho`.

This is intentionally a first benchmark ladder. Later milestones may replace the parameter estimation layer with maximum-likelihood, hierarchical Bayesian or time-decayed formulations, but those richer models must continue to run through the same cutoff and evaluation contracts.

## Feature ablation rule

When richer football state arrives, every important feature family should be tested incrementally against these baselines. Examples:

- score-only;
- + current squad state;
- + injuries/suspensions;
- + projected lineup;
- + tactical/coach state;
- + travel/weather;
- + market information.

A feature is not considered useful merely because the final model looks sophisticated. Its incremental effect on proper scores, calibration and uncertainty must be measured out of sample under the same information cutoff.
