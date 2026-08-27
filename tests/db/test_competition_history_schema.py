from sqlalchemy import CheckConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from tunix_football.db import competition_models as _competition_models  # noqa: F401
from tunix_football.db import models as _models  # noqa: F401
from tunix_football.db.base import Base


def _check_names(table_name: str) -> set[str]:
    table = Base.metadata.tables[table_name]
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint) and constraint.name is not None
    }


def test_competition_history_tables_are_registered() -> None:
    assert {
        "season_rule_versions",
        "season_club_participations",
        "match_revisions",
    } <= set(Base.metadata.tables)


def test_match_revision_semantics_are_database_invariants() -> None:
    checks = _check_names("match_revisions")

    assert "ck_match_revisions_positive_revision" in checks
    assert "ck_match_revisions_completed_requires_score" in checks
    assert "ck_match_revisions_unplayed_has_no_score" in checks


def test_season_history_stores_version_and_transition_metadata() -> None:
    rule_columns = set(Base.metadata.tables["season_rule_versions"].columns.keys())
    participation_columns = set(
        Base.metadata.tables["season_club_participations"].columns.keys()
    )

    assert {
        "competition_season_id",
        "version",
        "valid_from",
        "observed_at",
        "supersedes_id",
        "rules",
    } <= rule_columns
    assert {
        "competition_season_id",
        "club_id",
        "entry_type",
        "exit_type",
        "from_competition_id",
        "to_competition_id",
    } <= participation_columns


def test_competition_history_tables_compile_for_postgresql() -> None:
    dialect = postgresql.dialect()
    for table_name in (
        "season_rule_versions",
        "season_club_participations",
        "match_revisions",
    ):
        table = Base.metadata.tables[table_name]
        compiled = str(CreateTable(table).compile(dialect=dialect))
        assert f"CREATE TABLE {table_name}" in compiled
