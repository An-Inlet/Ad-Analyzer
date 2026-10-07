"""0083 frozen DDL matches metadata and refuses lossy retained lineage downgrade."""

import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.reported_feedback.candidate_models import statements
from sqlalchemy import Engine, inspect

from tests.migration_engine import migration_customer_engine as migration_customer_engine


def test_actual0083_empty_roundtrip(migration_customer_engine: Engine) -> None:
    engine = migration_customer_engine
    migration = importlib.import_module(
        "migrations.versions.20261007_0083_reported_rule_dependencies"
    )
    assert migration.SQL[engine.dialect.name] == statements(engine.dialect.name)
    with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        migration.downgrade()
        assert "reported_rule_candidate_dependencies" not in inspect(connection).get_table_names()
        migration.upgrade()
        foreign = inspect(connection).get_foreign_keys("reported_rule_candidate_dependencies")
        assert len(foreign) == 3
        assert all(value["options"]["ondelete"] == "CASCADE" for value in foreign)
