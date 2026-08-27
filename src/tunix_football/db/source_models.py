from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from tunix_football.db.base import Base, CreatedAtMixin


class SourceConfigRecord(CreatedAtMixin, Base):
    __tablename__ = "source_configs"

    source_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("sources.id", ondelete="CASCADE"),
        primary_key=True,
    )
    source_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(64), nullable=False)
    collector_version: Mapped[str] = mapped_column(String(64), nullable=False)
    request_policy: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    terms_status: Mapped[str] = mapped_column(String(32), nullable=False)
    commercial_use_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    robots_notes: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CollectorRunRecord(CreatedAtMixin, Base):
    __tablename__ = "collector_runs"
    __table_args__ = (
        CheckConstraint("records_count >= 0", name="records_count_nonnegative"),
        Index("ix_collector_runs_source_started", "source_id", "started_at"),
    )

    run_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    records_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parser_version: Mapped[str] = mapped_column(String(64), nullable=False)
    collector_version: Mapped[str] = mapped_column(String(64), nullable=False)
    failure_kind: Mapped[str | None] = mapped_column(String(32))
    error_message: Mapped[str | None] = mapped_column(Text)


class RawSourceRecord(CreatedAtMixin, Base):
    """Metadata envelope for immutable raw evidence kept in object storage."""

    __tablename__ = "raw_source_records"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "evidence_key",
            name="uq_raw_source_records_source_evidence_key",
        ),
        Index("ix_raw_source_records_source_observed", "source_id", "observed_at"),
        Index("ix_raw_source_records_hash", "content_sha256"),
    )

    record_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    collector_run_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("collector_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    )
    evidence_key: Mapped[str | None] = mapped_column(String(256))
    source_entity_id: Mapped[str | None] = mapped_column(String(256))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_url: Mapped[str | None] = mapped_column(String(1024))
    media_type: Mapped[str] = mapped_column(String(120), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_object_key: Mapped[str | None] = mapped_column(String(1024))
    parser_version: Mapped[str] = mapped_column(String(64), nullable=False)
    collector_version: Mapped[str] = mapped_column(String(64), nullable=False)
    request_context: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    verification_state: Mapped[str] = mapped_column(String(32), nullable=False)
