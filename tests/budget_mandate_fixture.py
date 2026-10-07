"""Actual imported history and configured reads, with zero prior production authority."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.api import customer_budget_mandates, customer_goals, customer_initial_planning
from app.collectors import owned_meta_budget
from app.customers.access import SESSION_COOKIE, CustomerPrincipal, digest
from app.customers.models import CustomerSession, CustomerUser
from app.planning_reporting import runtime as assembly
from app.settings import Settings, settings
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_budget_mandate_contracts import operating_policy
from tests.test_customer_identity import login
from tests.test_customer_optimization_api import headers
from tests.test_initial_planning_api import ready_history
from tests.test_planning_reporting_configuration import profile
from tests.test_social_optimization_http import Server


def first_customer(
    engine: Engine,
    configuration: Settings,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> Any:
    from tests import test_customer_goals

    alice, _, provider = replicas
    actor = login(alice, "budget-first:1")
    original_definition = test_customer_goals.definition
    today = datetime.now(UTC).date()
    monkeypatch.setattr(
        test_customer_goals,
        "definition",
        lambda store: original_definition(store).model_copy(
            update={
                "budget_start": today - timedelta(days=1),
                "budget_end": today + timedelta(days=30),
            }
        ),
    )
    with Session(engine) as db:
        user = db.get(CustomerUser, actor)
        session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
        assert user and session
        wid, gid, aid, cid, old_runtime, observations = ready_history(
            engine, configuration, monkeypatch, CustomerPrincipal(user, session), provider
        )
    alice.app.include_router(customer_goals.router)
    goal_root = f"/api/customer/v1/workspaces/{wid}/goals/{gid}"
    current_goal = alice.get(goal_root)
    assert current_goal.status_code == 200, current_goal.text
    edited = alice.put(
        goal_root,
        headers=headers(alice),
        json={"expected_revision": 1, "definition": current_goal.json()["definition"]},
    )
    assert edited.status_code == 200, edited.text
    goal_preview = alice.post(
        goal_root + "/preview", headers=headers(alice), json={"expected_revision": 2}
    )
    assert goal_preview.status_code == 200, goal_preview.text
    confirmed = alice.post(
        goal_root + "/confirm",
        headers=headers(alice),
        json={
            "expected_revision": 2,
            "preview_id": goal_preview.json()["preview_id"],
            "idempotency_key": "first-customer-budget-confirm",
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    configured = profile()
    profile_path = path / "profile.json"
    profile_path.write_text(configured.model_dump_json())
    monkeypatch.setattr(settings, "planning_reporting_profile_path", str(profile_path))
    monkeypatch.setattr(settings, "planning_reporting_profile_digest", configured.digest())
    policy = operating_policy().model_copy(
        update={"planning_reporting_profile_digest": configured.digest()}
    )
    policy_path = path / "budget-policy.json"
    policy_path.write_text(policy.model_dump_json())
    monkeypatch.setattr(settings, "budget_mandate_policy_path", str(policy_path))
    monkeypatch.setattr(settings, "budget_mandate_policy_digest", policy.digest())
    for name in (
        "meta_enabled",
        "meta_client_id",
        "meta_client_secret",
        "meta_token_encryption_key",
        "meta_redirect_uri",
    ):
        monkeypatch.setattr(settings, name, getattr(configuration, name))
    monkeypatch.setattr(assembly, "planning_clock", lambda: datetime.now(UTC))
    server = Server("meta_ads")
    server.meta_campaign["daily_budget"] = "1000"
    requests = []
    control: dict[str, Any] = {}

    def wire(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        requests.append(request)
        translated = str(request.url).replace("act_101", "act_123").replace("/201", "/5")
        response = server(httpx.Request("GET", translated, headers=request.headers))
        value = response.text.replace('"123"', '"101"').replace('"5"', '"201"')
        callback = control.pop("callback", None)
        if callback:
            callback()
        return httpx.Response(200, json=json.loads(value))

    monkeypatch.setattr(
        owned_meta_budget, "native_budget_transport", lambda: httpx.MockTransport(wire)
    )
    alice.app.include_router(customer_initial_planning.router)
    alice.app.include_router(customer_budget_mandates.router)
    root = f"/api/customer/v1/workspaces/{wid}/initial-planning"
    calibrated = alice.post(
        root + "/calibrations",
        headers=headers(alice),
        json={
            "observation_id": observations[-1],
            "goal_id": gid,
            "goal_revision": 2,
            "maximum_reported_cpa_micros": 10000000,
        },
    )
    assert calibrated.status_code == 200, calibrated.text
    selection = {"calibration_id": calibrated.json()["id"], "observation_id": observations[-1]}
    options = alice.post(root + "/native-options", headers=headers(alice), json=selection)
    assert options.status_code == 200, options.text
    assert options.json()["mandates"] == []
    selection["native_option_id"] = options.json()["options"][0]["id"]
    body = {
        "intent": {
            "selection": selection,
            "total_cap_micros": 50000000,
            "aggressiveness": "balanced",
        }
    }
    return alice, root, body, policy, requests, control, wid, server
