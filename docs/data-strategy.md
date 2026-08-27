# Data Strategy

## Objective

Build a proprietary, source-aware temporal football knowledge base without making the platform dependent on any single provider.

## Source classes

Potential source families include:

- federation and league sources
- official club sources
- transfer and market-value sources
- match/statistics providers
- injury and suspension sources
- odds/market consensus providers
- weather and travel data
- reputable news sources
- historical archives

Specific integrations must be reviewed for terms of service, licensing, robots policies, rate limits and commercial-use rights before production use.

## Pipeline

```text
collect → preserve raw → normalize → resolve entities → validate → canonicalize → emit event
```

Collectors must never silently overwrite raw evidence.

## Raw-first retention

Original source payloads should be written to object storage with metadata including source, fetch time, content hash, request context and parser version. This allows reprocessing when parsers or schemas improve.

## Provenance

Every canonical fact should be traceable back to one or more source observations.

Candidate provenance fields:

- source ID
- source URL or source-native identifier
- observed timestamp
- parser version
- confidence
- verification state
- raw-object reference

## Conflict resolution

Conflicting sources should not be resolved by last-write-wins. Resolution policy may consider:

1. official source authority;
2. source reliability history;
3. corroborating source count;
4. freshness;
5. structured-data quality;
6. manual review for high-impact conflicts.

## Source reliability

Reliability is a model input, not a hard-coded universal truth. Source reliability can evolve by domain: a source may be strong for transfers but weak for injury-return dates.

## Legal and commercial constraint

Technical accessibility does not imply redistribution or commercial-use rights. Data licensing is part of product architecture, not an afterthought.
