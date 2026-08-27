# Event Sourcing and Temporal Truth

## Why event sourcing?

Football changes through discrete events: transfers, registrations, injuries, recoveries, suspensions, coach changes, lineups and match outcomes. If only current state is stored, historical reconstruction becomes fragile and honest backtesting becomes difficult.

## Event contract

Each event should identify:

- event type
- canonical entity
- when the real-world event occurred
- when the system observed it
- validity window where applicable
- source/provenance
- confidence
- payload

## Two clocks

A critical distinction:

- `occurred_at` / `valid_from`: football-world time
- `observed_at`: system-knowledge time

Example: a player may have been injured during training at 10:00, but the club announcement may only be observed by our system at 14:30. A prediction generated at noon must not use the later announcement.

## Rebuilding state

Derived current state should be rebuildable from an ordered event history plus versioned reducers/state estimators. Expensive derived snapshots may be cached for performance, but the event log remains the historical evidence.

## Corrections

Source corrections should not erase history silently. A correction is a new observation/event that supersedes or invalidates prior canonical interpretation while preserving provenance.

## Backtesting rule

For a historical forecast cutoff `T`, only source observations with `observed_at <= T` may influence model inputs. This rule is non-negotiable and should be testable in code.
