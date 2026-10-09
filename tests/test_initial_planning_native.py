"""Exact nominal preview uses real Meta HTTP reads, never financial qualification."""

import json
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from app.api import customer_initial_planning as api
from app.customers.access import SESSION_COOKIE, CustomerPrincipal, digest
from app.customers.models import CustomerSession, CustomerUser
from app.executors.meta_optimization import MetaOptimizationTransport
from app.initial_planning.models import PreviewRow
from app.meta.models import MetaConnection
from app.publication import customer_intents, execution_mandates
from app.publication.contracts import fingerprint
from app.publication.customer_optimization_catalog import (
    ConfiguredOptimizationCatalog,
    NamedOptimizationTarget,
)
from app.publication.customer_optimization_contracts import CustomerOptimizationRuntime
from app.publication.execution_contracts import ProviderMandatePolicy
from app.publication.optimization_contracts import (
    MoneyContext,
    OptimizationContext,
    OptimizationTarget,
)
from app.publication.optimization_execution_contracts import OptimizationRuntime
from app.settings import Settings
from pydantic import SecretStr
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import login
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_initial_planning_api import ready_history
from tests.test_shopify_sales import configuration as configuration
from tests.test_social_optimization_http import Server


@pytest.mark.parametrize("change", [None, "session", "generation", "precision", "environment"])
def historical_contract_exact_native_preview_and_fresh_io_fences(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    change: str | None,
) -> None:
    alice, _, provider = replicas
    actor = login(alice, "alice:1")
    token = digest(alice.cookies[SESSION_COOKIE])
    with Session(customer_engine) as db:
        user, session = db.get(CustomerUser, actor), db.get(CustomerSession, token)
        assert user and session
        wid, gid, aid, _, runtime, observation_ids = ready_history(
            customer_engine, configuration, monkeypatch, CustomerPrincipal(user, session), provider
        )
    if change == "precision":
        assert runtime.configuration
        original = runtime.configuration
        rule = original.rules[0].model_copy(update={"budget_step_micros": 1})
        runtime = replace(runtime, configuration=original.model_copy(update={"rules": (rule,)}))
    server = Server("meta_ads")
    server.meta_campaign["daily_budget"] = "1000"
    armed = [False]
    reads = []

    def wire(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET", "preview cannot mutate a provider"
        reads.append(request.url.path)
        translated = str(request.url).replace("act_101", "act_123").replace("/201", "/5")
        response = server(httpx.Request("GET", translated, headers=request.headers))
        value = response.text.replace('"123"', '"101"').replace('"5"', '"201"')
        if armed[0]:
            armed[0] = False
            with Session(customer_engine) as db:
                if change == "session":
                    row = db.get(CustomerSession, token)
                    assert row
                    row.revoked_at = int(time.time())
                elif change == "generation":
                    source = db.scalar(
                        select(MetaConnection).where(MetaConnection.account_id == aid)
                    )
                    assert source
                    source.generation += 1
                db.commit()
        return httpx.Response(200, json=json.loads(value))

    with Session(customer_engine) as db:
        scope = customer_intents.account(db, wid, aid)
        db.rollback()
    now = datetime.now(UTC)
    money = MoneyContext(
        currency="USD",
        currency_exponent=2,
        account_timezone="UTC",
        period_start=now - timedelta(minutes=1),
        period_end=now + timedelta(hours=1),
    )
    target = OptimizationTarget(kind="campaign", external_id="201", campaign_id="201")
    context = OptimizationContext(
        scope=scope, access_token=SecretStr("offline-token"), expires_at=now + timedelta(hours=1)
    )
    adapter = MetaOptimizationTransport(transport=httpx.MockTransport(wire))
    state = adapter.read_current(scope, target, money, "e" * 32, 1, context, now)

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Preview must not request financial qualification or exposure")

    execution = OptimizationRuntime(
        "contract_test", forbidden, forbidden, lambda _: context, meta=adapter
    )
    catalog = ConfiguredOptimizationCatalog(
        execution,
        (
            NamedOptimizationTarget(
                fingerprint("inlet.optimization-catalog-scope.v1", scope.model_dump(mode="json")),
                "Exact Owned Campaign",
                "Owned Account",
                target,
                money,
                "e" * 32,
                1,
            ),
        ),
    )
    runtime = replace(
        runtime, native=CustomerOptimizationRuntime(execution, catalog, runtime.clock)
    )
    policy = ProviderMandatePolicy(
        environment="contract_test",
        workspace_id=wid,
        goal_id=gid,
        goal_revision=1,
        currency="USD",
        time_zone="UTC",
        starts_at=money.period_start,
        ends_at=money.period_end,
        accounts=[scope],
        total_cap_micros=50_000_000,
        per_plan_cap_micros=50_000_000,
        positive_change_cap_micros=5_000_000,
        action_limit=1,
        cooldown_seconds=60,
        freshness_seconds=60,
        aggressiveness_percent=10,
        allowed_purposes=["existing_campaign_optimize"],
        allowed_target_set_digest=state.budget_owner.target_set_digest(),
        campaign_and_creative_policy="new_exact_review_required",
        activation_policy="separate_exact_approval",
    )
    with Session(customer_engine) as db:
        row = execution_mandates.revise(db, wid, policy, actor, lambda: now)
        execution_mandates.consent(
            db, wid, row.id, row.revision, policy.digest(), actor, lambda: now
        )
        mandate_id = row.id
    alice.app.include_router(api.router)
    alice.app.dependency_overrides[api.get_initial_planning_runtime] = lambda: runtime
    root = f"/api/customer/v1/workspaces/{wid}/initial-planning"
    calibrated = alice.post(
        root + "/calibrations",
        headers=headers(alice),
        json={
            "observation_id": observation_ids[-1],
            "goal_id": gid,
            "goal_revision": 1,
            "maximum_reported_cpa_micros": 10000000,
        },
    )
    assert calibrated.status_code == 200, calibrated.text
    body = {"calibration_id": calibrated.json()["id"], "observation_id": observation_ids[-1]}
    options = alice.post(root + "/native-options", headers=headers(alice), json=body)
    assert options.status_code == 200, options.text
    assert options.json()["mandates"][0]["id"] == mandate_id
    body.update(
        choice=options.json()["options"][0]["choice"], mandate_id=mandate_id, mandate_revision=1
    )
    if change == "environment":
        assert runtime.native is not None
        runtime = replace(
            runtime,
            native=replace(runtime.native, execution=replace(execution, environment="live")),
        )
    armed[0] = change in {"session", "generation"}
    result = alice.post(root + "/previews", headers=headers(alice), json=body)
    if change:
        assert result.status_code in {401, 409}, result.text
    else:
        assert result.status_code == 200, result.text
        value = result.json()
        assert (value["before_budget_micros"], value["after_budget_micros"]) == (10000000, 11000000)
        assert value["direction"] == "increase" and value["review_available"] is False
        assert "provider_acceptance_unverified" in value["reasons"]
    assert server.posts == [] and reads
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(PreviewRow)) == (0 if change else 1)
