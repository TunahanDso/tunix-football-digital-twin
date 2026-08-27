from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from tunix_football.squad.contracts import SquadHistorySeed


class SquadHistoryError(ValueError):
    pass


def load_squad_history(path: str | Path) -> SquadHistorySeed:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SquadHistoryError(f"cannot load squad history from {path}: {exc}") from exc

    try:
        return SquadHistorySeed.model_validate(payload)
    except ValidationError as exc:
        raise SquadHistoryError(f"invalid squad history: {exc}") from exc
