# Domain Model

## Core entities

The canonical domain is built around stable internal identifiers rather than source-specific names or IDs.

Initial entity families:

- Player
- Club
- Squad
- Contract
- Transfer
- Injury
- Suspension
- Coach
- CoachTenure
- Competition
- CompetitionSeason
- Fixture
- Match
- Lineup
- Appearance
- MatchEvent
- Stadium
- Referee
- Source
- SourceEntity
- ModelVersion
- ModelSnapshot
- Scenario
- SimulationRun

## Canonical identity

Every real-world entity receives a TUNIX canonical ID. External identifiers are mapped separately:

```text
SourceEntity
  source = "provider-x"
  source_id = "12345"
  canonical_entity_id = <uuid>
```

This prevents spelling changes, aliases and provider migrations from contaminating the model layer.

## Temporal facts

Facts that change over time should carry enough temporal metadata to reconstruct historical truth. At minimum:

- `valid_from`
- `valid_until`
- `observed_at`
- `source_id`
- `confidence`
- `version`

## Team state

The first latent team-state contract contains dimensions for:

- attack
- defence
- buildup
- transition
- pressing
- set pieces
- depth
- fitness
- fatigue
- chemistry
- confidence
- uncertainty

These are contracts, not final formulas. Their definitions and scales must be learned, documented and versioned through research.

## Player state

Player intelligence will eventually be role-aware and multi-dimensional. Candidate dimensions include finishing, shot generation, chance creation, progression, dribbling, press resistance, pressing, defending, aerial ability, physical state, availability and form.

A player's contribution is contextual:

```text
impact = f(player, team, role, coach, formation, league, opposition)
```

The system must not equate market value directly with football ability.
