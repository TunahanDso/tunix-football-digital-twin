"""Add append-only temporal player squad membership history.

Revision ID: 0008_squad_membership_history
Revises: 0007_evidence_identity
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_squad_membership_history"
down_revision: str | None = "0007_evidence_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "player_squad_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("club_id", sa.Uuid(), nullable=False),
        sa.Column("spell_key", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.entity_id"],
            name="fk_player_squad_memberships_club_id_clubs",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["players.entity_id"],
            name="fk_player_squad_memberships_player_id_players",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_player_squad_memberships"),
        sa.UniqueConstraint(
            "player_id",
            "club_id",
            "spell_key",
            name="uq_squad_memberships_player_club_spell",
        ),
    )
    op.create_index(
        "ix_squad_memberships_club_player",
        "player_squad_memberships",
        ["club_id", "player_id"],
    )
    op.create_index(
        "ix_squad_memberships_player",
        "player_squad_memberships",
        ["player_id"],
    )

    op.create_table(
        "player_squad_membership_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("revision_kind", sa.String(length=32), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("membership_kind", sa.String(length=32), nullable=False),
        sa.Column("shirt_number", sa.Integer(), nullable=True),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("raw_record_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "revision_number > 0",
            name="ck_player_squad_membership_revisions_positive_revision",
        ),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from",
            name="ck_player_squad_membership_revisions_valid_time_window",
        ),
        sa.CheckConstraint(
            "shirt_number IS NULL OR shirt_number > 0",
            name="ck_player_squad_membership_revisions_positive_shirt_number",
        ),
        sa.ForeignKeyConstraint(
            ["membership_id"],
            ["player_squad_memberships.id"],
            name=(
                "fk_player_squad_membership_revisions_membership_id_"
                "player_squad_memberships"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["raw_record_id"],
            ["raw_source_records.record_id"],
            name=(
                "fk_player_squad_membership_revisions_raw_record_id_"
                "raw_source_records"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            name="fk_player_squad_membership_revisions_source_id_sources",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_player_squad_membership_revisions",
        ),
        sa.UniqueConstraint(
            "membership_id",
            "revision_number",
            name="uq_squad_membership_revisions_membership_revision",
        ),
    )
    op.create_index(
        "ix_squad_membership_revisions_membership_observed",
        "player_squad_membership_revisions",
        ["membership_id", "observed_at"],
    )
    op.create_index(
        "ix_squad_membership_revisions_validity",
        "player_squad_membership_revisions",
        ["valid_from", "valid_until"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_squad_membership_revisions_validity",
        table_name="player_squad_membership_revisions",
    )
    op.drop_index(
        "ix_squad_membership_revisions_membership_observed",
        table_name="player_squad_membership_revisions",
    )
    op.drop_table("player_squad_membership_revisions")
    op.drop_index(
        "ix_squad_memberships_player",
        table_name="player_squad_memberships",
    )
    op.drop_index(
        "ix_squad_memberships_club_player",
        table_name="player_squad_memberships",
    )
    op.drop_table("player_squad_memberships")
