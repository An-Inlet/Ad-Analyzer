"""0075 actual PostgreSQL DDL roundtrip in an isolated schema."""

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text

from tests.migration_engine import migration_customer_engine as migration_customer_engine


def test_0075_actual_tables_triggers_and_roundtrip(migration_customer_engine: Engine) -> None:
    if migration_customer_engine.dialect.name != "postgresql":
        pytest.skip("actual Alembic roundtrip requires isolated PostgreSQL")
    tables = {
        "initial_observations",
        "initial_calibration_runs",
        "initial_calibration_dependencies",
        "initial_plan_previews",
    }
    assert tables <= set(inspect(migration_customer_engine).get_table_names())
    with migration_customer_engine.connect() as connection:
        names = set(
            connection.scalars(
                text(
                    "SELECT tgname FROM pg_trigger "
                    "WHERE tgrelid = 'initial_observations'::regclass AND NOT tgisinternal"
                )
            )
        )
        assert {
            "initial_observations_guard",
            "initial_observations_immutable",
            "initial_observations_erase",
        } <= names
    command.downgrade(Config("alembic.ini"), "20261006_0074")
    assert not tables & set(inspect(migration_customer_engine).get_table_names())
    command.upgrade(Config("alembic.ini"), "20261006_0075")
    assert tables <= set(inspect(migration_customer_engine).get_table_names())
