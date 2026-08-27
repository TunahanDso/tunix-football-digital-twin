from sqlalchemy import CheckConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from tunix_football.db import backtest_models as _backtest_models  # noqa: F401
from tunix_football.db import models as _models  # noqa: F401
from tunix_football.db.base import Base


def _check_names(table_name: str) -> set[str]:
    table = Base.metadata.tables[table_name]
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint) and constraint.name is not None
    }


def test_backtest_tables_are_registered() -> None:
    assert {"backtest_runs", "backtest_predictions"} <= set(Base.metadata.tables)


def test_prediction_cutoffs_are_database_invariants() -> None:
    checks = _check_names("backtest_predictions")

    assert "ck_backtest_predictions_data_before_prediction" in checks
    assert "ck_backtest_predictions_market_before_prediction" in checks


def test_backtest_outputs_store_reproducibility_metadata() -> None:
    run_columns = set(Base.metadata.tables["backtest_runs"].columns.keys())
    prediction_columns = set(Base.metadata.tables["backtest_predictions"].columns.keys())

    assert {
        "model_version_id",
        "config_hash",
        "data_snapshot_hash",
        "seed",
        "lead_time_seconds",
        "max_data_cutoff",
    } <= run_columns
    assert {
        "prediction_cutoff",
        "data_cutoff",
        "market_snapshot_at",
        "train_match_count",
    } <= prediction_columns


def test_backtest_tables_compile_for_postgresql() -> None:
    dialect = postgresql.dialect()
    for table_name in ("backtest_runs", "backtest_predictions"):
        table = Base.metadata.tables[table_name]
        compiled = str(CreateTable(table).compile(dialect=dialect))
        assert f"CREATE TABLE {table_name}" in compiled
