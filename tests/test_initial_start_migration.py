"""Actual 0085 composite owner/erasure topology and empty lossless downgrade."""

import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.initial_planning.start_triggers import statements
from sqlalchemy import Engine, inspect

from tests.migration_engine import migration_customer_engine as migration_customer_engine


def test_actual_0085_roundtrip(migration_customer_engine: Engine) -> None:
    engine = migration_customer_engine
    migration = importlib.import_module(
        "migrations.versions.20261007_0085_initial_rule_session_starts"
    )
    with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        migration.downgrade()
        assert "initial_rule_session_starts" not in inspect(connection).get_table_names()
        migration.upgrade()
        keys = inspect(connection).get_foreign_keys("initial_rule_session_starts")
        assert len(keys) == 2
        assert {key["options"]["ondelete"] for key in keys} == {"SET NULL", "RESTRICT"}
        assert all(len(key["constrained_columns"]) == 2 for key in keys)
        assert all(
            sql in migration.SQL[engine.dialect.name] for sql in statements(engine.dialect.name)
        )
