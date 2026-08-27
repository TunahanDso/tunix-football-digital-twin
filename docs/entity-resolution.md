# Entity Resolution Core

## Why this exists

External football sources do not share one universal identity system. The same real-world entity can appear under different provider IDs, spellings, abbreviations, transliterations and historical names.

TUNIX therefore owns canonical identity independently of every provider.

```text
Provider A: 12345 / Fenerbahçe
Provider B: club_77 / Fenerbahce SK
Provider C: FB / FENERBAHÇE
                 ↓
        TUNIX canonical UUID
```

A provider identifier is evidence about identity, never the canonical primary key.

## Resolution pipeline

```text
SourceRecord
   ↓
normalize name
   ↓
filter by entity type
   ↓
active canonical names + time-valid aliases
   ↓
exact match layer
   ↓
attribute / similarity scoring
   ↓
MATCHED | AMBIGUOUS | UNMATCHED
                 ↓
          audit decision
                 ↓
      review queue if ambiguous
```

## Conservative automation

False merges are more dangerous than unresolved records. A wrong merge can contaminate years of player, transfer and match history.

The resolver therefore follows conservative rules:

- exactly one active normalized name match can resolve automatically;
- two entities with the same exact name are ambiguous unless additional evidence separates them;
- fuzzy candidates require both a high score and sufficient margin over the runner-up;
- low-confidence cases remain unresolved;
- ambiguous cases can be converted into explicit review cases;
- no resolution path invents or replaces a TUNIX canonical UUID with a provider ID.

## Name normalization

Normalization is deterministic and separate from display names. It currently handles:

- Unicode decomposition;
- diacritic removal for matching;
- Turkish `İ/ı` normalization;
- case folding;
- punctuation and whitespace normalization.

For example:

```text
Fenerbahçe SK → fenerbahce sk
Fenerbahce SK → fenerbahce sk
İstanbul      → istanbul
```

Canonical display values are never rewritten by this process.

## Time-aware aliases

Aliases have validity windows.

A historical club name can be correct for a 2013 source record and wrong for a 2026 source record. The resolver only considers an alias when the request's `as_of` time falls inside the alias validity interval.

This keeps historical ingestion reproducible and prevents old names from becoming permanent universal synonyms.

## Candidate scoring

The initial scorer is deliberately transparent and deterministic. It combines:

- normalized name similarity;
- birth-date agreement/conflict when available;
- country agreement/conflict when available.

This is a baseline, not the final intelligence layer. The `CandidateScorer` protocol lets us later replace or augment it with learned probabilistic models without changing the resolver contract.

## Ambiguity

A result is not forced into a match just because one candidate ranks first.

Automatic resolution requires:

```text
top_score >= auto_match_threshold
AND
(top_score - second_score) >= ambiguity_margin
```

Otherwise sufficiently plausible candidates become an `AMBIGUOUS` result and enter manual review.

## Audit persistence

Migration `0003_entity_resolution_core` adds four structures:

### `entity_aliases`

Time-aware aliases attached to stable canonical UUIDs, with source, observation time and confidence.

### `entity_resolution_decisions`

Every persisted decision can retain:

- source and source-native external ID;
- raw source record reference;
- input and normalized names;
- resolved canonical UUID, if any;
- status and method;
- score;
- decision timestamp and actor;
- structured rationale.

### `entity_resolution_review_cases`

Explicit queue state for ambiguous decisions. A case can remain pending, be assigned and later retain resolution notes rather than disappearing after manual intervention.

### `entity_identity_events`

Merge/split corrections are audit events. Historical decisions should not be silently rewritten when we later discover that two canonical identities were duplicates or that one identity accidentally represented multiple people.

## Current limits

The first resolver does not yet use:

- squad membership overlap;
- transfer history;
- position;
- height;
- nationality sets;
- team context at observation time;
- provider-specific trust weights;
- learned embeddings or probabilistic linkage models.

Those can be added only after the deterministic baseline is measurable.

## Principle

> **It is better to say “ambiguous” than to poison the football graph with a confident-looking wrong identity.**
