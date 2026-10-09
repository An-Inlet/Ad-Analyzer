"""Real0079 DDL retains owned authority and refuses lossy downgrade."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from app.initial_planning.budget_mandate_models import BudgetMandatePreparationRow
from app.lifecycle.export_serializers import serialize
from app.settings import Settings
from sqlalchemy import Engine, inspect, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from tests.budget_mandate_fixture import first_customer
from tests.migration_engine import migration_customer_engine as migration_customer_engine
from tests.optimization_origin_historical_schema import legacy_origin as legacy_origin
from tests.retired_migration_producer import retained_budget_preparation_fixture
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration


@pytest.fixture
def customer_engine(migration_customer_engine: Engine) -> Engine:
    return migration_customer_engine


def test_real_schema_retains_preparation(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    legacy_origin: Callable[[Engine], None],
) -> None:
    table = "initial_budget_mandate_preparations"
    if customer_engine.dialect.name == "postgresql":
        command.downgrade(Config("alembic.ini"), "20261007_0078")
        assert table not in inspect(customer_engine).get_table_names()
        command.upgrade(Config("alembic.ini"), "20261007_0079")
        retained_budget_preparation_fixture(customer_engine, tmp_path / "budget-producer")
    else:
        alice, root, body, *_ = first_customer(
            customer_engine, configuration, tmp_path, monkeypatch, replicas
        )
        prepared = alice.post(root + "/budget-mandates", headers=headers(alice), json=body)
        assert prepared.status_code == 201, prepared.text
    with Session(customer_engine) as db:
        row = db.scalar(select(BudgetMandatePreparationRow))
        assert row is not None
        values = {c.name: getattr(row, c.name) for c in row.__table__.columns}
        exported, omitted = serialize(table, values)
        assert exported["document"] == row.document and not omitted
        invalid = {**values, "workspace_id": row.workspace_id + 1}
        exported, omitted = serialize(table, invalid)
        assert "document" not in exported and "document" in omitted
    for statement in (
        f"UPDATE {table} SET digest=digest",
        f"DELETE FROM {table}",
    ):
        with pytest.raises(DBAPIError), customer_engine.begin() as connection:
            connection.execute(text(statement))
    if customer_engine.dialect.name == "postgresql":
        with pytest.raises(RuntimeError, match="cannot discard retained"):
            command.downgrade(Config("alembic.ini"), "20261007_0078")
        with customer_engine.connect() as connection:
            assert connection.scalar(text(f"SELECT count(*) FROM {table}")) == 1
