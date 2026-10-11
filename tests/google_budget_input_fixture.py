"""Original receipt and opaque option from actual private configured APIs."""

import copy
from pathlib import Path
from typing import Any

import pytest
from app.api import customer_planning_budget_owners
from app.settings import Settings
from sqlalchemy import Engine

from tests.google_budget_owner_discovery_fixture import acquired_owner_catalog
from tests.test_customer_optimization_api import headers


def ready_inputs(
    engine: Engine, config: Settings, replicas: Any, patch: pytest.MonkeyPatch, path: Path
) -> tuple[Any, dict[str, Any], list[tuple[str, str]], dict[str, Any]]:
    fixture, catalog, calls = acquired_owner_catalog(engine, config, replicas, patch, path)
    alice, _, _ = replicas
    alice.app.include_router(customer_planning_budget_owners.router)
    root = f"/api/customer/v1/workspaces/{fixture.basis.workspace_id}/planning"
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
    option = discovery.json()["owners"][0]
    target = option["representative"]
    body = copy.deepcopy(fixture.body)
    body["request_key"] = "google-owner-input-create"
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
