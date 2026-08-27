from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from tunix_football.db import resolution_models as _resolution_models  # noqa: F401
from tunix_football.db import source_models as _source_models  # noqa: F401
from tunix_football.db.base import Base
from tunix_football.resolution.normalization import normalize_name
from tunix_football.resolution.resolver import EntityResolver
from tunix_football.resolution.types import (
    AliasRecord,
    CanonicalCandidate,
    EntityType,
    ResolutionMethod,
    ResolutionRequest,
    ResolutionStatus,
)


def request(
    name: str,
    *,
    entity_type: EntityType = EntityType.PLAYER,
    as_of: datetime | None = None,
    birth_date: date | None = None,
) -> ResolutionRequest:
    return ResolutionRequest(
        source_key="synthetic.demo",
        source_entity_id="external-1",
        entity_type=entity_type,
        name=name,
        as_of=as_of or datetime(2026, 8, 27, tzinfo=UTC),
        birth_date=birth_date,
    )


def test_turkish_diacritics_normalize_deterministically() -> None:
    assert normalize_name("Fenerbahçe SK") == normalize_name("Fenerbahce SK")
    assert normalize_name("İstanbul") == normalize_name("istanbul")


def test_spelling_variant_resolves_to_stable_canonical_uuid() -> None:
    canonical_id = uuid4()
    candidate = CanonicalCandidate(
        canonical_entity_id=canonical_id,
        entity_type=EntityType.CLUB,
        canonical_name="Fenerbahçe SK",
    )

    result = EntityResolver().resolve(
        request("Fenerbahce SK", entity_type=EntityType.CLUB),
        [candidate],
    )

    assert result.status is ResolutionStatus.MATCHED
    assert result.method is ResolutionMethod.EXACT
    assert result.resolved_entity_id == canonical_id


def test_same_name_players_are_never_silently_accepted() -> None:
    candidates = [
        CanonicalCandidate(
            canonical_entity_id=uuid4(),
            entity_type=EntityType.PLAYER,
            canonical_name="Mehmet Yılmaz",
            birth_date=date(1998, 1, 1),
        ),
        CanonicalCandidate(
            canonical_entity_id=uuid4(),
            entity_type=EntityType.PLAYER,
            canonical_name="Mehmet Yılmaz",
            birth_date=date(2002, 7, 4),
        ),
    ]

    result = EntityResolver().resolve(request("Mehmet Yılmaz"), candidates)

    assert result.status is ResolutionStatus.AMBIGUOUS
    assert result.resolved_entity_id is None
    assert len(result.candidates) == 2
    review = EntityResolver().to_review_case(result)
    assert len(review.candidates) == 2


def test_birth_date_can_disambiguate_same_name_players() -> None:
    expected_id = uuid4()
    candidates = [
        CanonicalCandidate(
            canonical_entity_id=expected_id,
            entity_type=EntityType.PLAYER,
            canonical_name="Mehmet Yılmaz",
            birth_date=date(1998, 1, 1),
        ),
        CanonicalCandidate(
            canonical_entity_id=uuid4(),
            entity_type=EntityType.PLAYER,
            canonical_name="Mehmet Yılmaz",
            birth_date=date(2002, 7, 4),
        ),
    ]

    result = EntityResolver().resolve(
        request("Mehmet Yılmaz", birth_date=date(1998, 1, 1)),
        candidates,
    )

    assert result.status is ResolutionStatus.MATCHED
    assert result.method is ResolutionMethod.ATTRIBUTE
    assert result.resolved_entity_id == expected_id


def test_historical_alias_only_matches_inside_its_valid_window() -> None:
    canonical_id = uuid4()
    alias = AliasRecord(
        canonical_entity_id=canonical_id,
        entity_type=EntityType.CLUB,
        alias="İstanbul Büyükşehir Belediyespor",
        valid_from=datetime(2007, 1, 1, tzinfo=UTC),
        valid_until=datetime(2014, 6, 1, tzinfo=UTC),
    )
    candidate = CanonicalCandidate(
        canonical_entity_id=canonical_id,
        entity_type=EntityType.CLUB,
        canonical_name="Başakşehir FK",
        aliases=[alias],
    )

    historical = EntityResolver().resolve(
        request(
            "Istanbul Buyuksehir Belediyespor",
            entity_type=EntityType.CLUB,
            as_of=datetime(2013, 5, 1, tzinfo=UTC),
        ),
        [candidate],
    )
    current = EntityResolver().resolve(
        request(
            "Istanbul Buyuksehir Belediyespor",
            entity_type=EntityType.CLUB,
            as_of=datetime(2026, 8, 27, tzinfo=UTC),
        ),
        [candidate],
    )

    assert historical.status is ResolutionStatus.MATCHED
    assert historical.resolved_entity_id == canonical_id
    assert current.resolved_entity_id is None


def test_resolution_audit_tables_are_registered() -> None:
    assert {
        "entity_aliases",
        "entity_resolution_decisions",
        "entity_resolution_review_cases",
        "entity_identity_events",
    } <= set(Base.metadata.tables)
