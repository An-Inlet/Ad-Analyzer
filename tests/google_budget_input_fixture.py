"""Original receipt and opaque option from actual private configured APIs."""

import copy
from pathlib import Path
from typing import Any

import pytest
from app.api import customer_planning_budget_owners
from app.settings import Settings
from sqlalchemy import Engine

from tests.google_budget_owner_discovery_fixture import (
    OwnerCatalogResponseControl,
    acquired_owner_catalog,
)
from tests.test_customer_optimization_api import headers


def ready_inputs(
    engine: Engine,
    config: Settings,
    replicas: Any,
    patch: pytest.MonkeyPatch,
    path: Path,
    *,
    partial: bool = False,
    response_control: OwnerCatalogResponseControl | None = None,
) -> tuple[Any, dict[str, Any], list[tuple[str, str]], dict[str, Any]]:
    fixture, catalog, calls = acquired_owner_catalog(
        engine, config, replicas, patch, path, partial=partial, response_control=response_control
    )
    alice, _, _ = replicas
    alice.app.include_router(customer_planning_budget_owners.router)
    root = f"/api/customer/v1/workspaces/{fixture.basis.workspace_id}/planning"
    before_calls = len(calls)
    discovery = alice.post(
        root + "/google-budget-owners",
        headers=headers(alice),
        json=dict(
            account_id=fixture.basis.account_id,
            catalog_composite_digest=catalog["composite_digest"],
            reporting_window=fixture.body["inputs"]["reporting_window"],
        ),
    )
    assert discovery.status_code == 200, discovery.text
    assert len(calls) == before_calls
    body = copy.deepcopy(fixture.body)
    body["request_key"] = "google-owner-input-create"
    if partial:
        view = discovery.json()
        assert view["status"] == "unavailable" and view["owners"] == []
        assert view["reason"] == "google_budget_owner_unavailable"
        assert view["recovery"] == "Read fresh targets and review the full affected campaigns."
        body["inputs"]["google_daily_budget_intents"] = []
        return fixture, body, calls, catalog
    assert discovery.json()["status"] == "available"
    option = discovery.json()["owners"][0]
    target = option["representative"]
    body["inputs"]["scenario_intents"] = [
        dict(
            key="owner-test",
            title="Customer owner hypothesis",
            allocations=[
                dict(
                    target={
                        key: target[key] if key != "account_id" else target["account"]["account_id"]
                        for key in ("account_id", "canonical_entity_key", "selection_key")
                    },
                    amount_micros=100_000_000,
                )
            ],
            unallocated_micros=900_000_000,
        )
    ]
    body["inputs"]["google_daily_budget_intents"] = [
        {
            key: option[key]
            for key in (
                "account_id",
                "owner_selection_id",
                "expected_observation_digest",
                "expected_owner_facts_digest",
                "currency",
                "cadence",
                "unit",
            )
        }
        | dict(scenario_key="owner-test", requested_amount_micros=5_000_000)
    ]
    return fixture, body, calls, catalog
