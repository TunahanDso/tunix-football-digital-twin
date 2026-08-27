"""Add source registry configuration, collector runs and raw evidence metadata.

Revision ID: 0002_source_ingestion_framework
Revises: 0001_canonical_temporal_schema
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_source_ingestion_framework"
down_revision: str | None = "0001_canonical_temporal_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_configs",
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_kind", sa.String(length=40), nullable=False),
        sa.Column("parser_version", sa.String(length=64), nullable=False),
        sa.Column("collector_version", sa.String(length=64), nullable=False),
        sa.Column("request_policy", sa.JSON(), nullable=False),
        sa.Column("terms_status", sa.String(length=32), nullable=False),
        sa.Column("commercial_use_approved", sa.Boolean(), nullable=False),
        sa.Column("robots_notes", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            name="fk_source_configs_source_id_sources",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("source_id", name="pk_source_configs"),
    )

    op.create_table(
        "collector_runs",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("records_count", sa.Integer(), nullable=False),
        sa.Column("parser_version", sa.String(length=64), nullable=False),
        sa.Column("collector_version", sa.String(length=64), nullable=False),
        sa.Column("failure_kind", sa.String(length=32), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "records_count >= 0",
            name="ck_collector_runs_records_count_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            name="fk_collector_runs_source_id_sources",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("run_id", name="pk_collector_runs"),
    )
    op.create_index(
        "ix_collector_runs_source_started",
        "collector_runs",
        ["source_id", "started_at"],
    )

    op.create_table(
        "raw_source_records",
        sa.Column("record_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("collector_run_id", sa.Uuid(), nullable=False),
        sa.Column("source_entity_id", sa.String(length=256), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_url", sa.String(length=1024), nullable=True),
        sa.Column("media_type", sa.String(length=120), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("raw_object_key", sa.String(length=1024), nullable=True),
        sa.Column("parser_version", sa.String(length=64), nullable=False),
        sa.Column("collector_version", sa.String(length=64), nullable=False),
        sa.Column("request_context", sa.JSON(), nullable=False),
        sa.Column("verification_state", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["collector_run_id"],
            ["collector_runs.run_id"],
            name="fk_raw_source_records_collector_run_id_collector_runs",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            name="fk_raw_source_records_source_id_sources",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("record_id", name="pk_raw_source_records"),
    )
    op.create_index(
        "ix_raw_source_records_hash",
        "raw_source_records",
        ["content_sha256"],
    )
    op.create_index(
        "ix_raw_source_records_source_observed",
        "raw_source_records",
        ["source_id", "observed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_raw_source_records_source_observed",
        table_name="raw_source_records",
    )
    op.drop_index("ix_raw_source_records_hash", table_name="raw_source_records")
    op.drop_table("raw_source_records")
    op.drop_index("ix_collector_runs_source_started", table_name="collector_runs")
    op.drop_table("collector_runs")
    op.drop_table("source_configs")
