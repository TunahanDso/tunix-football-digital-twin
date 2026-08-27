from __future__ import annotations

from sqlalchemy import CheckConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from tunix_football.db import models as _models  # noqa: F401
from tunix_football.db.base import Base


def _check_names(table_name: str) -> set[str]:
    table = Base.metadata.tables[table_name]
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint) and constraint.name is not None
    }


def test_canonical_tables_are_registered() -> None:
    expected = {
        "canonical_entities",
        "players",
        "clubs",
        "coaches",
        "competitions",
        "competition_seasons",
        "matches",
        "sources",
        "source_entities",
        "football_events",
        "model_versions",
        "model_snapshots",
    }

    assert expected <= set(Base.metadata.tables)


def test_provider_ids_do_not_leak_into_player_identity() -> None:
    player_columns = set(Base.metadata.tables["players"].columns.keys())

    assert "entity_id" in player_columns
    assert "source_id" not in player_columns
    assert "external_id" not in player_columns


def test_temporal_tables_enforce_valid_time_windows() -> None:
    assert "ck_source_entities_valid_time_window" in _check_names("source_entities")
    assert "ck_football_events_valid_time_window" in _check_names("football_events")


def test_probability_fields_have_database_checks() -> None:
    assert "ck_sources_reliability_probability" in _check_names("sources")
    assert "ck_source_entities_confidence_probability" in _check_names(
        "source_entities"
    )
    assert "ck_football_events_confidence_probability" in _check_names(
        "football_events"
    )


def test_model_snapshots_record_data_cutoff() -> None:
    columns = set(Base.metadata.tables["model_snapshots"].columns.keys())

    assert {"model_version_id", "entity_id", "as_of", "data_cutoff", "state"} <= columns


def test_every_table_compiles_for_postgresql() -> None:
    dialect = postgresql.dialect()

    for table in Base.metadata.sorted_tables:
        compiled = str(CreateTable(table).compile(dialect=dialect))
        assert f"CREATE TABLE {table.name}" in compiled
