from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TeamState(BaseModel):
    """A time-indexed latent representation of a football team's current state.

    Values are intentionally dimensionless in M0. Their statistical meaning and
    calibration will be learned and versioned by later model iterations.
    """

    club_id: UUID
    as_of: datetime
    model_version: str

    attack: float
    defence: float
    buildup: float
    transition: float
    pressing: float
    set_piece: float
    depth: float
    fitness: float
    fatigue: float
    chemistry: float
    confidence: float

    uncertainty: float = Field(ge=0.0)
