from __future__ import annotations

from tunix_football.resolution.normalization import normalize_name
from tunix_football.resolution.scoring import CandidateScorer, SimilarityScorer
from tunix_football.resolution.types import (
    CanonicalCandidate,
    ResolutionMethod,
    ResolutionRequest,
    ResolutionResult,
    ResolutionStatus,
    ReviewCase,
)


class EntityResolver:
    def __init__(
        self,
        *,
        scorer: CandidateScorer | None = None,
        auto_match_threshold: float = 0.92,
        ambiguity_margin: float = 0.08,
        review_floor: float = 0.65,
    ) -> None:
        self._scorer = scorer or SimilarityScorer()
        self._auto_match_threshold = auto_match_threshold
        self._ambiguity_margin = ambiguity_margin
        self._review_floor = review_floor

    def resolve(
        self,
        request: ResolutionRequest,
        candidates: list[CanonicalCandidate],
    ) -> ResolutionResult:
        typed_candidates = [
            candidate
            for candidate in candidates
            if candidate.entity_type is request.entity_type
        ]
        if not typed_candidates:
            return ResolutionResult(
                status=ResolutionStatus.UNMATCHED,
                method=ResolutionMethod.NONE,
                request=request,
                explanation="no candidates exist for the requested entity type",
            )

        exact = [
            candidate
            for candidate in typed_candidates
            if self._has_exact_active_name(request, candidate)
        ]
        if len(exact) == 1:
            candidate = exact[0]
            return ResolutionResult(
                status=ResolutionStatus.MATCHED,
                method=ResolutionMethod.EXACT,
                request=request,
                resolved_entity_id=candidate.canonical_entity_id,
                candidates=[self._scorer.score(request, candidate)],
                explanation="one canonical entity has an exact active normalized name",
            )

        scored_pool = exact if exact else typed_candidates
        ranked = sorted(
            (self._scorer.score(request, candidate) for candidate in scored_pool),
            key=lambda candidate: candidate.score,
            reverse=True,
        )

        if len(exact) > 1 and request.birth_date is None and request.country_code is None:
            return ResolutionResult(
                status=ResolutionStatus.AMBIGUOUS,
                method=ResolutionMethod.EXACT,
                request=request,
                candidates=ranked[:5],
                explanation="multiple canonical entities share the same exact name",
            )

        top = ranked[0]
        second_score = ranked[1].score if len(ranked) > 1 else 0.0
        margin = top.score - second_score

        if top.score >= self._auto_match_threshold and (
            len(ranked) == 1 or margin >= self._ambiguity_margin
        ):
            method = ResolutionMethod.ATTRIBUTE if exact else ResolutionMethod.FUZZY
            return ResolutionResult(
                status=ResolutionStatus.MATCHED,
                method=method,
                request=request,
                resolved_entity_id=top.canonical_entity_id,
                candidates=ranked[:5],
                explanation=(
                    f"top candidate passed threshold with score={top.score:.3f} "
                    f"and margin={margin:.3f}"
                ),
            )

        review_candidates = [
            candidate for candidate in ranked if candidate.score >= self._review_floor
        ][:5]
        if review_candidates:
            return ResolutionResult(
                status=ResolutionStatus.AMBIGUOUS,
                method=ResolutionMethod.FUZZY,
                request=request,
                candidates=review_candidates,
                explanation="candidate evidence is insufficient for safe automatic resolution",
            )

        return ResolutionResult(
            status=ResolutionStatus.UNMATCHED,
            method=ResolutionMethod.NONE,
            request=request,
            candidates=ranked[:5],
            explanation="no candidate reached the manual-review floor",
        )

    def to_review_case(self, result: ResolutionResult) -> ReviewCase:
        if result.status is not ResolutionStatus.AMBIGUOUS:
            raise ValueError("only ambiguous results belong in the review queue")
        return ReviewCase(
            request=result.request,
            candidates=result.candidates,
            reason=result.explanation,
        )

    @staticmethod
    def _has_exact_active_name(
        request: ResolutionRequest,
        candidate: CanonicalCandidate,
    ) -> bool:
        requested = normalize_name(request.name)
        if requested == normalize_name(candidate.canonical_name):
            return True
        return any(
            alias.entity_type is request.entity_type
            and alias.is_valid_at(request.as_of)
            and requested == normalize_name(alias.alias)
            for alias in candidate.aliases
        )
