"""Actual confirmed goals with invalid local budget boundaries cannot create authority."""

from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from app.api import customer_goals
from app.api.customer_goals import router
from app.commerce.models import CommerceStore
from app.production_runtime.optimization_origin_models import OptimizationMandatePreparationRow
from app.publication.execution_models import (
    ProviderExecutionMandate,
    ProviderExecutionRevision,
    ProviderPeriodLedger,
)
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.configured_optimization_fixture import configured
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize(
    "zone,start,end",
    [
        ("America/Havana", date(2026, 11, 1), date(2026, 11, 2)),
        ("Pacific/Apia", date(2011, 12, 30), date(2011, 12, 31)),
    ],
)
def test_invalid_budget_midnight_returns409_without_authority(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    zone: str,
    start: date,
    end: date,
) -> None:
    alice, base, query, wire, control = configured(
        customer_engine, configuration, tmp_path, monkeypatch, replicas, "google_ads"
    )
    wid = int(base.split("/workspaces/")[1].split("/")[0])
    # Fixture verified commerce basis, not an override of the financial converter.
    with Session(customer_engine) as db:
        store = db.scalar(select(CommerceStore).where(CommerceStore.workspace_id == wid))
        assert store
        store.time_zone = zone
        db.commit()
    monkeypatch.setattr(customer_goals, "datetime", SimpleNamespace(now=lambda _: NOW))
    alice.app.include_router(router)
    goal_root = base.removesuffix("/execution") + "/goals/" + query["goal_id"]
    response = alice.get(goal_root)
    assert response.status_code == 200, response.text
    definition = response.json()["definition"]
    for key in ("target_window", "baseline_window"):
        definition[key]["time_zone"] = zone
    definition.update(budget_start=start.isoformat(), budget_end=end.isoformat())
    revised = alice.put(
        goal_root,
        headers=headers(alice),
        json={"expected_revision": query["goal_revision"], "definition": definition},
    )
    assert revised.status_code == 200, revised.text
    revision = revised.json()["revision"]
    preview = alice.post(
        goal_root + "/preview", headers=headers(alice), json={"expected_revision": revision}
    )
    assert preview.status_code == 200, preview.text
    confirmed = alice.post(
        goal_root + "/confirm",
        headers=headers(alice),
        json={
            "expected_revision": revision,
            "preview_id": preview.json()["preview_id"],
            "idempotency_key": "financial-boundary-confirm",
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    selected = {**query, "goal_revision": revision, "option_id": "a" * 64}
    rejected = alice.post(
        base + "/optimization/budget-mandates",
        headers=headers(alice),
        json={
            "intent": {
                "selection": selected,
                "total_cap_micros": 50_000_000,
                "aggressiveness": "balanced",
            }
        },
    )
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["detail"] == "financial_budget_period_unavailable"
    assert control["opened"] == control["factory"] == 0 and not wire.calls
    with Session(customer_engine) as db:
        for model in (
            ProviderExecutionMandate,
            ProviderExecutionRevision,
            ProviderPeriodLedger,
            OptimizationMandatePreparationRow,
        ):
            assert db.scalar(select(func.count()).select_from(model)) == 0
