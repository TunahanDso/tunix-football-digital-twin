"""Canonical entity resolution for source-shaped football evidence."""

from tunix_football.resolution.normalization import normalize_name
from tunix_football.resolution.resolver import EntityResolver
from tunix_football.resolution.types import (
    CanonicalCandidate,
    ResolutionRequest,
    ResolutionResult,
    ResolutionStatus,
)

__all__ = [
    "CanonicalCandidate",
    "EntityResolver",
    "ResolutionRequest",
    "ResolutionResult",
    "ResolutionStatus",
    "normalize_name",
]
