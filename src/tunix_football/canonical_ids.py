from __future__ import annotations

from uuid import NAMESPACE_URL, UUID, uuid5

TUNIX_FOOTBALL_NAMESPACE = uuid5(
    NAMESPACE_URL,
    "https://tunix.dev/football-digital-twin/canonical",
)


def canonical_id(kind: str, key: str) -> UUID:
    """Derive a stable TUNIX UUID from a TUNIX-owned logical key."""

    normalized_kind = kind.strip().lower()
    normalized_key = key.strip().lower()
    if not normalized_kind:
        raise ValueError("canonical ID kind cannot be empty")
    if not normalized_key:
        raise ValueError("canonical ID key cannot be empty")
    return uuid5(TUNIX_FOOTBALL_NAMESPACE, f"{normalized_kind}:{normalized_key}")
