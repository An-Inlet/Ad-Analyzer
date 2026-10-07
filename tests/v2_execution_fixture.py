"""Actual configured v2 planning and separate optimization consent, offline HTTP only."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.ads.models import AdvertisingAccount
from app.api import customer_execution, customer_initial_execution
from app.goals.models import Goal
from app.production_runtime import optimization_assembly
from app.settings import Settings
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.budget_mandate_fixture import first_customer
from tests.configured_optimization_fixture import configured
from tests.test_customer_optimization_api import headers


def ready(
    engine: Engine,
    configuration: Settings,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> Any:
    alice, root, body, _, requests, controls, wid, server = first_customer(
        engine, configuration, path, monkeypatch, replicas
    )
    with Session(engine) as db:
        goal = db.scalar(select(Goal).where(Goal.workspace_id == wid))
        account = db.scalar(
            select(AdvertisingAccount).where(
                AdvertisingAccount.workspace_id == wid, AdvertisingAccount.platform == "meta_ads"
            )
        )
        assert goal and account
        query = dict(goal_id=goal.id, goal_revision=goal.revision, account_id=account.id)
    base = root.removesuffix("/initial-planning") + "/execution"
    _, _, _, _, optimization_control = configured(
        engine, configuration, path, monkeypatch, replicas, "meta_ads", (alice, base, query)
    )
    monkeypatch.setattr(optimization_assembly, "utc_now", lambda: datetime.now(UTC))

    def wire(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        callback = controls.pop("callback", None)
        if callback:
            callback()
        translated = str(request.url).replace("act_101", "act_123").replace("/201", "/5")
        endpoint = request.url.path
        if endpoint.endswith("/campaigns"):
            response = httpx.Response(200, json={"data": [server.meta_campaign]})
        elif endpoint == "/v26.0/act_101/adsets":
            response = httpx.Response(200, json={"data": [server.meta_child]})
        elif request.url.params.get("fields") == "id,account_id,name":
            response = httpx.Response(
                200, json={"id": "5", "account_id": "123", "name": "Owned Campaign"}
            )
        else:
            try:
                response = server(
                    httpx.Request(
                        request.method, translated, headers=request.headers, content=request.content
                    )
                )
            finally:
                # Authentication form fields are not persisted native campaign settings.
                server.meta_campaign.pop("appsecret_proof", None)
                server.meta_child.pop("appsecret_proof", None)
        return httpx.Response(
            response.status_code,
            json=json.loads(response.text.replace('"123"', '"101"').replace('"5"', '"201"')),
        )

    monkeypatch.setattr(
        optimization_assembly,
        "optimization_execution_transport",
        lambda _: httpx.MockTransport(wire),
    )
    alice.app.include_router(customer_initial_execution.router)
    alice.app.include_router(customer_execution.router)
    prepared = alice.post(root + "/budget-mandates", json=body, headers=headers(alice))
    assert prepared.status_code == 201, prepared.text
    planning = prepared.json()
    selection = body["intent"]["selection"]
    consent = alice.post(
        root + "/budget-mandates/" + planning["mandate_id"] + "/consent",
        headers=headers(alice),
        json={
            "selection": selection,
            "expected_revision": planning["revision"],
            "policy_digest": planning["policy_digest"],
            "preparation_digest": planning["preparation_digest"],
        },
    )
    assert consent.status_code == 200, consent.text
    preview = alice.post(
        root + "/previews",
        headers=headers(alice),
        json={
            "calibration_id": selection["calibration_id"],
            "observation_id": selection["observation_id"],
            "choice": {"option_id": selection["native_option_id"]},
            "mandate_id": planning["mandate_id"],
            "mandate_revision": planning["revision"],
        },
    )
    assert preview.status_code == 200, preview.text
    return alice, root, base, query, preview.json(), server, controls, planning
