"""Actual 0084 DDL and composite ownership, independent of ORM construction."""

import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.initial_planning.automatic_triggers import TABLES, statements
from sqlalchemy import Engine, inspect

from tests.migration_engine import migration_customer_engine as migration_customer_engine


def test_actual0084_empty_roundtrip(migration_customer_engine: Engine) -> None:
    engine = migration_customer_engine
    migration = importlib.import_module(
        "migrations.versions.20261007_0084_initial_rule_dependencies"
    )
    with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        migration.downgrade()
        assert not set(TABLES) & set(inspect(connection).get_table_names())
        migration.upgrade()
        inspector = inspect(connection)
        for table in TABLES:
            for statement in statements(table, engine.dialect.name):
                assert statement in migration.SQL[engine.dialect.name]
        parent = inspector.get_foreign_keys("initial_rule_candidate_dependencies")
        assert len(parent) == 5
        assert all(item["options"]["ondelete"] == "CASCADE" for item in parent)
        inputs = inspector.get_foreign_keys("initial_rule_candidate_observations")
        assert len(inputs) == 2
        assert all(len(item["constrained_columns"]) == 4 for item in inputs)
        protected = inspector.get_foreign_keys("initial_rule_admission_origins")
        assert len(protected) == 2
        assert all(item["options"]["ondelete"] == "RESTRICT" for item in protected)
