"""Add entity aliases, resolution decisions, review queue and identity audit.

Revision ID: 0003_entity_resolution_core
Revises: 0002_source_ingestion_framework
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_entity_resolution_core"
down_revision: str | None = "0002_source_ingestion_framework"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "entity_aliases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("canonical_entity_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("alias", sa.String(length=200), nullable=False),
        sa.Column("normalized_alias", sa.String(length=200), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_entity_aliases_confidence_probability",
        ),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_from IS NULL OR valid_until > valid_from",
            name="ck_entity_aliases_valid_time_window",
        ),
        sa.ForeignKeyConstraint(
            ["canonical_entity_id"],
            ["canonical_entities.id"],
            name="fk_entity_aliases_canonical_entity_id_canonical_entities",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            name="fk_entity_aliases_source_id_sources",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_entity_aliases"),
    )
    op.create_index(
        "ix_entity_aliases_lookup",
        "entity_aliases",
        ["entity_type", "normalized_alias"],
    )
    op.create_index(
        "ix_entity_aliases_entity",
        "entity_aliases",
        ["canonical_entity_id", "valid_from"],
    )

    op.create_table(
        "entity_resolution_decisions",
        sa.Column("decision_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("raw_record_id", sa.Uuid(), nullable=True),
        sa.Column("external_id", sa.String(length=256), nullable=True),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("input_name", sa.String(length=200), nullable=False),
        sa.Column("normalized_name", sa.String(length=200), nullable=False),
        sa.Column("resolved_entity_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("method", sa.String(length=24), nullable=False),
        sa.Column("top_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by", sa.String(length=120), nullable=False),
        sa.Column("rationale", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "top_score IS NULL OR (top_score >= 0 AND top_score <= 1)",
            name="ck_entity_resolution_decisions_top_score_probability",
        ),
        sa.ForeignKeyConstraint(
            ["raw_record_id"],
            ["raw_source_records.record_id"],
            name="fk_entity_resolution_decisions_raw_record_id_raw_source_records",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_entity_id"],
            ["canonical_entities.id"],
            name="fk_resolution_decisions_resolved_entity",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            name="fk_entity_resolution_decisions_source_id_sources",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("decision_id", name="pk_entity_resolution_decisions"),
    )
    op.create_index(
        "ix_resolution_decisions_source_external",
        "entity_resolution_decisions",
        ["source_id", "external_id"],
    )
    op.create_index(
        "ix_resolution_decisions_resolved",
        "entity_resolution_decisions",
        ["resolved_entity_id", "decided_at"],
    )

    op.create_table(
        "entity_resolution_review_cases",
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("decision_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("assigned_to", sa.String(length=120), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["decision_id"],
            ["entity_resolution_decisions.decision_id"],
            name="fk_resolution_review_cases_decision",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("case_id", name="pk_entity_resolution_review_cases"),
        sa.UniqueConstraint(
            "decision_id",
            name="uq_entity_resolution_review_cases_decision_id",
        ),
    )
    op.create_index(
        "ix_resolution_review_cases_status",
        "entity_resolution_review_cases",
        ["status", "created_at"],
    )

    op.create_table(
        "entity_identity_events",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=24), nullable=False),
        sa.Column("subject_entity_id", sa.Uuid(), nullable=False),
        sa.Column("target_entity_id", sa.Uuid(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("reason", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["subject_entity_id"],
            ["canonical_entities.id"],
            name="fk_entity_identity_events_subject_entity_id_canonical_entities",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["target_entity_id"],
            ["canonical_entities.id"],
            name="fk_entity_identity_events_target_entity_id_canonical_entities",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("event_id", name="pk_entity_identity_events"),
    )
    op.create_index(
        "ix_entity_identity_events_subject",
        "entity_identity_events",
        ["subject_entity_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_entity_identity_events_subject",
        table_name="entity_identity_events",
    )
    op.drop_table("entity_identity_events")
    op.drop_index(
        "ix_resolution_review_cases_status",
        table_name="entity_resolution_review_cases",
    )
    op.drop_table("entity_resolution_review_cases")
    op.drop_index(
        "ix_resolution_decisions_resolved",
        table_name="entity_resolution_decisions",
    )
    op.drop_index(
        "ix_resolution_decisions_source_external",
        table_name="entity_resolution_decisions",
    )
    op.drop_table("entity_resolution_decisions")
    op.drop_index("ix_entity_aliases_entity", table_name="entity_aliases")
    op.drop_index("ix_entity_aliases_lookup", table_name="entity_aliases")
    op.drop_table("entity_aliases")
