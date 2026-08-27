from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from tunix_football.db.base import Base, CreatedAtMixin


class EntityAliasRecord(CreatedAtMixin, Base):
    __tablename__ = "entity_aliases"
    __table_args__ = (
        CheckConstraint(
            "valid_until IS NULL OR valid_from IS NULL OR valid_until > valid_from",
            name="valid_time_window",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="confidence_probability",
        ),
        Index("ix_entity_aliases_lookup", "entity_type", "normalized_alias"),
        Index("ix_entity_aliases_entity", "canonical_entity_id", "valid_from"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    canonical_entity_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("canonical_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    alias: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(200), nullable=False)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("sources.id", ondelete="SET NULL"),
    )
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)


class ResolutionDecisionRecord(CreatedAtMixin, Base):
    __tablename__ = "entity_resolution_decisions"
    __table_args__ = (
        CheckConstraint(
            "top_score IS NULL OR (top_score >= 0 AND top_score <= 1)",
            name="top_score_probability",
        ),
        Index("ix_resolution_decisions_source_external", "source_id", "external_id"),
        Index("ix_resolution_decisions_resolved", "resolved_entity_id", "decided_at"),
    )

    decision_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    raw_record_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("raw_source_records.record_id", ondelete="SET NULL"),
    )
    external_id: Mapped[str | None] = mapped_column(String(256))
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    input_name: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(200), nullable=False)
    resolved_entity_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("canonical_entities.id", ondelete="SET NULL"),
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    method: Mapped[str] = mapped_column(String(24), nullable=False)
    top_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_by: Mapped[str] = mapped_column(String(120), nullable=False)
    rationale: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class ResolutionReviewCaseRecord(CreatedAtMixin, Base):
    __tablename__ = "entity_resolution_review_cases"
    __table_args__ = (
        Index("ix_resolution_review_cases_status", "status", "created_at"),
    )

    case_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    decision_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("entity_resolution_decisions.decision_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    assigned_to: Mapped[str | None] = mapped_column(String(120))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_notes: Mapped[str | None] = mapped_column(Text)


class EntityIdentityEventRecord(CreatedAtMixin, Base):
    """Audits identity merges/splits without rewriting historical decisions."""

    __tablename__ = "entity_identity_events"
    __table_args__ = (
        Index("ix_entity_identity_events_subject", "subject_entity_id", "occurred_at"),
    )

    event_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    subject_entity_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("canonical_entities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    target_entity_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("canonical_entities.id", ondelete="RESTRICT"),
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    reason: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
