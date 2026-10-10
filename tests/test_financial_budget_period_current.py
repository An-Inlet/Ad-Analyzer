"""Actual current goal flow, separate route denial and exact financial-period rejection."""

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from app.api import customer_goals
from app.api.customer_goals import router as goals_router
from app.api.customer_optimization import router as optimization_router
from app.api.customer_optimization_runtime import get_configured_customer_optimization_runtime
from app.commerce.models import CommerceStore
from app.database.session import Base
from app.goals import service as goals
from app.goals.models import Goal
from app.goals.schemas import ConfirmInput, GoalDefinition
from app.production_runtime.optimization_assembly import period
from app.production_runtime.optimization_origin_models import OptimizationMandatePreparationRow
from app.publication.budget_period import financial_budget_period
from app.publication.execution_models import (
    ProviderExecutionMandate,
    ProviderExecutionRevision,
    ProviderPeriodLedger,
)
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.configured_draft_retained_fixture import retained_configured_draft_fixture
from tests.configured_google_read_fixture import configured_customer
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration


def financial_rows(engine: Engine) -> dict[str, list[dict[str, Any]]]:
    with engine.connect() as db:
        return {
            table.name: [dict(row) for row in db.execute(select(table)).mappings()]
            for table in Base.metadata.sorted_tables
            if table.name.startswith("provider_")
            or table.name == "optimization_mandate_preparations"
        }


@pytest.mark.planning_boundary
@pytest.mark.parametrize(
    "zone,start,end",
    [
        ("America/Havana", date(2026, 11, 1), date(2026, 11, 2)),
        ("Pacific/Apia", date(2011, 12, 30), date(2011, 12, 31)),
    ],
)
def test_current_invalid_budget_midnight_goal_and_route_boundaries(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    zone: str,
    start: date,
    end: date,
) -> None:
    with retained_configured_draft_fixture(
        customer_engine, tmp_path / "retained", "google_ads"
    ) as (engine, ids, media):
        clients = cast(Any, replicas).__wrapped__(engine, monkeypatch)
        try:
            alice, base, _, _, _, server, requests, control = configured_customer(
                engine, configuration, media, monkeypatch, clients, ids
            )
            wid = ids.workspace_id
            # Exact initial current goal setup from configured(...), with the genuine actor.
            with Session(engine) as db:
                goal = db.scalars(select(Goal).where(Goal.workspace_id == wid)).one()
                initial_definition = GoalDefinition.model_validate(
                    goals.current(db, goal).definition
                )
                goals.revise(
                    db,
                    goal,
                    initial_definition.model_copy(update={"budget_start": NOW.date()}),
                    ids.actor_id,
                    NOW,
                )
                preview = goals.preview(db, goal, NOW)
                goals.confirm(
                    db,
                    goal,
                    ConfirmInput(
                        expected_revision=goal.revision,
                        preview_id=preview.id,
                        idempotency_key="configured-optimization-goal",
                    ),
                    NOW,
                    actor_id=ids.actor_id,
                )
                db.commit()
                query: dict[str, Any] = dict(
                    goal_id=goal.id, goal_revision=goal.revision, account_id=ids.account_id
                )
                store = db.scalar(select(CommerceStore).where(CommerceStore.workspace_id == wid))
                assert store
                store.time_zone = zone
                db.commit()
            monkeypatch.setattr(customer_goals, "datetime", SimpleNamespace(now=lambda _: NOW))
            alice.app.include_router(goals_router)
            alice.app.include_router(optimization_router)
            runtime_calls = 0

            def forbidden_runtime() -> None:
                nonlocal runtime_calls
                runtime_calls += 1
                raise AssertionError("Current planning denial must precede runtime construction")

            alice.app.dependency_overrides[get_configured_customer_optimization_runtime] = (
                forbidden_runtime
            )
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
            preview_response = alice.post(
                goal_root + "/preview", headers=headers(alice), json={"expected_revision": revision}
            )
            assert preview_response.status_code == 200, preview_response.text
            confirmed = alice.post(
                goal_root + "/confirm",
                headers=headers(alice),
                json={
                    "expected_revision": revision,
                    "preview_id": preview_response.json()["preview_id"],
                    "idempotency_key": "financial-boundary-confirm",
                },
            )
            assert confirmed.status_code == 200, confirmed.text
            before = financial_rows(engine)
            with Session(engine) as db:
                current = db.get(Goal, query["goal_id"])
                assert current and current.workspace_id == wid and current.revision == revision
                retained = goals.current(db, current)
                assert current.confirmed_preview_id == preview_response.json()["preview_id"]
                assert retained.confirmed_at is not None and retained.confirmed_by == ids.actor_id
                persisted = GoalDefinition.model_validate(retained.definition)
                assert persisted.budget_start == start and persisted.budget_end == end
                assert (
                    persisted.target_window.time_zone == persisted.baseline_window.time_zone == zone
                )
            for convert in (financial_budget_period, period):
                with pytest.raises(HTTPException) as caught:
                    convert(persisted)
                assert caught.value.status_code == 409
                assert caught.value.detail == "financial_budget_period_unavailable"
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
            assert rejected.json()["detail"] == "advertising_writes_disabled_in_planning_mvp"
            assert runtime_calls == 0 and control["transports_opened"] == 0 and not requests
            assert server.posts == server.activations == 0
            assert financial_rows(engine) == before
            with Session(engine) as db:
                for model in (
                    ProviderExecutionMandate,
                    ProviderExecutionRevision,
                    ProviderPeriodLedger,
                    OptimizationMandatePreparationRow,
                ):
                    assert db.scalar(select(func.count()).select_from(model)) == 0
            (tmp_path / "current-result.json").write_text(
                json.dumps(
                    dict(
                        confirmed=confirmed.json(),
                        persisted_definition=persisted.model_dump(mode="json"),
                        route_rejection=rejected.json(),
                        converter_reason="financial_budget_period_unavailable",
                        runtime_calls=runtime_calls,
                        provider_requests=len(requests),
                        provider_posts=server.posts,
                    ),
                    indent=2,
                )
            )
        finally:
            try:
                clients[0].close()
            finally:
                clients[1].close()
