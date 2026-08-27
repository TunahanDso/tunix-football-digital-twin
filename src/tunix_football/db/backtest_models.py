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
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from tunix_football.db.base import Base, CreatedAtMixin


class BacktestRunRecord(CreatedAtMixin, Base):
    __tablename__ = "backtest_runs"
    __table_args__ = (
        CheckConstraint("lead_time_seconds > 0", name="positive_lead_time"),
        CheckConstraint("seed >= 0", name="nonnegative_seed"),
        Index("ix_backtest_runs_model_started", "model_key", "started_at"),
    )

    run_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    model_version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("model_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    model_key: Mapped[str] = mapped_column(String(80), nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    data_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lead_time_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    max_data_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BacktestPredictionRecord(CreatedAtMixin, Base):
    __tablename__ = "backtest_predictions"
    __table_args__ = (
        UniqueConstraint("run_id", "match_id", name="uq_backtest_predictions_run_match"),
        CheckConstraint(
            "data_cutoff <= prediction_cutoff",
            name="data_before_prediction",
        ),
        CheckConstraint(
            "market_snapshot_at IS NULL OR market_snapshot_at <= prediction_cutoff",
            name="market_before_prediction",
        ),
        CheckConstraint(
            "home_win_probability >= 0 AND home_win_probability <= 1",
            name="home_probability_range",
        ),
        CheckConstraint(
            "draw_probability >= 0 AND draw_probability <= 1",
            name="draw_probability_range",
        ),
        CheckConstraint(
            "away_win_probability >= 0 AND away_win_probability <= 1",
            name="away_probability_range",
        ),
        Index("ix_backtest_predictions_cutoff", "prediction_cutoff"),
    )

    prediction_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("backtest_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    )
    match_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("matches.id", ondelete="CASCADE"),
        nullable=False,
    )
    prediction_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    train_match_count: Mapped[int] = mapped_column(Integer, nullable=False)
    home_win_probability: Mapped[Decimal] = mapped_column(Numeric(10, 8), nullable=False)
    draw_probability: Mapped[Decimal] = mapped_column(Numeric(10, 8), nullable=False)
    away_win_probability: Mapped[Decimal] = mapped_column(Numeric(10, 8), nullable=False)
    expected_home_goals: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    expected_away_goals: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    actual_home_goals: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_away_goals: Mapped[int] = mapped_column(Integer, nullable=False)
    market_snapshot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    market_home_probability: Mapped[Decimal | None] = mapped_column(Numeric(10, 8))
    market_draw_probability: Mapped[Decimal | None] = mapped_column(Numeric(10, 8))
    market_away_probability: Mapped[Decimal | None] = mapped_column(Numeric(10, 8))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
