"""Current optimization discovery from the exact original 10m policy and retained goal."""

from pathlib import Path
from typing import Any, cast

import pytest
from app.settings import Settings
from sqlalchemy import Engine

from tests.optimization_current_read_fixture import configured
from tests.optimization_source_retained_fixture import retained_optimization_source_fixture
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.planning_boundary
def test_current_optimization_owned_read(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with retained_optimization_source_fixture(customer_engine, tmp_path / "retained") as (
        engine,
        ids,
        media,
    ):
        clients = cast(Any, replicas).__wrapped__(engine, monkeypatch)
        try:
            alice, base, query, wire, control = configured(
                engine, configuration, media, monkeypatch, clients, ids
            )
            result = alice.post(
                base + "/optimization/target-options", json=query, headers=headers(alice)
            )
            assert result.status_code == 200, result.text
            assert result.json()["options"] and wire.calls
            assert control["opened"] == control["closed"] > 0
            assert not wire.google.writes
            denied = alice.post(base + "/optimization/mandates", json={}, headers=headers(alice))
            assert denied.status_code == 409
            assert denied.json()["detail"] == "advertising_writes_disabled_in_planning_mvp"
        finally:
            clients[0].close()
            clients[1].close()
