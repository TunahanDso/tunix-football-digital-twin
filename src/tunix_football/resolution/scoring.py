from __future__ import annotations

from difflib import SequenceMatcher
from typing import Protocol

from tunix_football.resolution.normalization import normalize_name
from tunix_football.resolution.types import (
    CandidateScore,
    CanonicalCandidate,
    ResolutionRequest,
)


class CandidateScorer(Protocol):
    def score(
        self,
        request: ResolutionRequest,
        candidate: CanonicalCandidate,
    ) -> CandidateScore: ...


class SimilarityScorer:
    """Conservative deterministic scorer used before learned resolution models."""

    def score(
        self,
        request: ResolutionRequest,
        candidate: CanonicalCandidate,
    ) -> CandidateScore:
        request_name = normalize_name(request.name)
        names = [candidate.canonical_name]
        names.extend(
            alias.alias
            for alias in candidate.aliases
            if alias.entity_type is request.entity_type and alias.is_valid_at(request.as_of)
        )
        name_score = max(
            SequenceMatcher(None, request_name, normalize_name(name)).ratio()
            for name in names
        )

        score = name_score
        reasons = [f"name={name_score:.3f}"]

        if request.birth_date is not None and candidate.birth_date is not None:
            if request.birth_date == candidate.birth_date:
                score = min(1.0, score + 0.06)
                reasons.append("birth_date=match")
            else:
                score = max(0.0, score - 0.20)
                reasons.append("birth_date=conflict")

        if request.country_code is not None and candidate.country_code is not None:
            if request.country_code.upper() == candidate.country_code.upper():
                score = min(1.0, score + 0.02)
                reasons.append("country=match")
            else:
                score = max(0.0, score - 0.04)
                reasons.append("country=conflict")

        return CandidateScore(
            canonical_entity_id=candidate.canonical_entity_id,
            score=score,
            name_score=name_score,
            reasons=tuple(reasons),
        )
