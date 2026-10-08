"""Unpatched planning artifact: owned reads succeed; execution intents have zero effect."""

import inspect
from types import SimpleNamespace
from typing import Any

import pytest
from app import advertising_capabilities
from app.api import (
    customer_candidates,
    customer_execution,
    customer_initial_execution,
    customer_initial_planning,
    customer_mandates,
    customer_optimization,
    customer_planning_catalog,
    customer_session_automation,
    customer_social_execution,
)
from app.customers.models import CustomerMembership, CustomerUser
from app.publication.execution_models import (
    ProviderExecutionApproval,
    ProviderExecutionAttempt,
    ProviderExecutionRun,
    ProviderExposureReservation,
)
from app.workspaces.models import Workspace
from fastapi import Response
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import login
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration

GUARDED = (
    (
        customer_execution,
        (
            "prepare_creation",
            "prepare_activation",
            "approve",
            "start_run",
            "advance",
            "create_mandate",
            "edit_mandate",
            "consent",
        ),
    ),
    (
        customer_optimization,
        (
            "initial_review",
            "repeat_review",
            "create_mandate",
            "edit_mandate",
            "consent",
            "prepare_customer_budget",
            "consent_customer_budget",
        ),
    ),
    (customer_social_execution, ("create_review",)),
    (customer_mandates, ("review", "claim", "dispatch")),
    (customer_initial_planning, ("prepare_review",)),
    (customer_initial_execution, ("prepare", "options")),
    (customer_session_automation, ("start", "initial_options")),
    (customer_candidates, ("review",)),
)


def owned_workspace(db: Session, actor: str) -> int:
    row = Workspace(slug="planning-owner", name="Planning", client_name="Planning", status="active")
    db.add(row)
    db.flush()
    db.add(CustomerMembership(user_id=actor, workspace_id=row.id, role="owner"))
    db.commit()
    return row.id


def test_direct_route_intents_stop_before_runtime_or_financial_effects(
    customer_engine: Engine,
    replicas: Any,
) -> None:
    client, _, _ = replicas
    actor = login(client, "planning-owner:1")
    with Session(customer_engine) as db:
        wid = owned_workspace(db, actor)
        principal: Any = SimpleNamespace(user=db.get(CustomerUser, actor))
        for module, names in GUARDED:
            for name in names:
                handler = getattr(module, name)
                # Runtime and request body are unusable sentinels: no retained execution
                # implementation may be entered. The real capability guard is not patched.
                args = dict.fromkeys(inspect.signature(handler).parameters, None)
                args.update(workspace_id=wid, db=db, principal=principal)
                with pytest.raises(advertising_capabilities.AdvertisingWritesDisabled):
                    handler(**args)
        execution = SimpleNamespace(
            environment="live",
            live_enabled=True,
            google=object(),
            meta=object(),
            tiktok=object(),
            replacement_reader=object(),
        )
        injected: Any = SimpleNamespace(
            creation=execution, execution=execution, catalog=object(), activation=object()
        )
        cap = customer_execution.capabilities(wid, principal, db, injected, Response())
        assert not cap["advertising_writes_enabled"] and not cap["activation_available"]
        assert all(not p["available"] for p in cap["providers"])
        opt = customer_optimization.capabilities(wid, principal, db, injected, Response())
        assert not opt["catalog_available"] and not opt["advertising_writes_enabled"]
        auto = customer_session_automation.capabilities(wid, principal, db, injected, Response())
        assert not auto.available and not auto.policies
        assert not db.new and not db.dirty
        for model in (
            ProviderExecutionApproval,
            ProviderExecutionAttempt,
            ProviderExecutionRun,
            ProviderExposureReservation,
        ):
            assert db.scalar(select(func.count()).select_from(model)) == 0


def test_actual_owned_catalog_history_and_forged_execution_http(
    customer_engine: Engine,
    replicas: Any,
) -> None:
    client, outsider, _ = replicas
    actor = login(client, "planning-owner:1")
    login(outsider, "outsider:1")
    for c in (client, outsider):
        c.app.include_router(customer_planning_catalog.router)
        c.app.include_router(customer_execution.router)
    with Session(customer_engine) as db:
        wid = owned_workspace(db, actor)
    root = f"/api/customer/v1/workspaces/{wid}"
    catalog = client.get(root + "/planning/accounts")
    assert catalog.status_code == 200 and catalog.json() == {"accounts": [], "complete": True}
    assert catalog.headers["cache-control"] == "no-store"
    assert outsider.get(root + "/planning/accounts").status_code in {403, 404}
    assert client.get(root + "/execution/runs").json() == []
    cases = (
        (
            "/execution/reviews/" + "a" * 32 + "/approval",
            {"review_digest": "b" * 64, "plan_digest": "c" * 64},
        ),
        ("/execution/reviews/" + "a" * 32 + "/runs", None),
        ("/execution/runs/" + "a" * 32 + "/advance", None),
    )
    for path, body in cases:
        denied = client.post(root + path, json=body, headers=headers(client))
        assert denied.status_code == 409, denied.text
        assert denied.json()["detail"] == "advertising_writes_disabled_in_planning_mvp"
        assert client.post(root + path, json=body).status_code == 403
        assert outsider.post(root + path, json=body, headers=headers(outsider)).status_code in {
            403,
            404,
        }
    assert client.delete("/api/customer/v1/session", headers=headers(client)).status_code == 204
    assert client.get(root + "/planning/accounts").status_code == 401


def test_owned_catalog_filters_inactive_sources_and_rechecks_membership(
    customer_engine: Engine,
    replicas: Any,
    configuration: Any,
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.ads.models import AdvertisingAccount
    from app.workspaces.models import WorkspaceIntegration

    from tests.budget_mandate_fixture import first_customer

    client, _, _, _, _, _, wid, server = first_customer(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
    )
    client.app.include_router(customer_planning_catalog.router)
    path = f"/api/customer/v1/workspaces/{wid}/planning/accounts"
    result = client.get(path)
    assert result.status_code == 200, result.text
    choices = result.json()["accounts"]
    assert len(choices) == 1 and choices[0]["platform"] == "meta_ads"
    with Session(customer_engine) as db:
        account = db.get(AdvertisingAccount, choices[0]["id"])
        assert account and account.workspace_id == wid
        integration = db.get(WorkspaceIntegration, account.connection_id)
        assert integration and integration.workspace_id == wid
        integration.status = "revoked"
        db.commit()
    filtered = client.get(path)
    assert filtered.status_code == 200 and filtered.json()["accounts"] == []
    with Session(customer_engine) as db:
        member = db.scalar(select(CustomerMembership).where(CustomerMembership.workspace_id == wid))
        assert member
        member.status = "suspended"
        db.commit()
    assert client.get(path).status_code in {403, 404}
    assert not server.posts


def test_route_denial_precedes_runtime_and_media_dependencies(
    customer_engine: Engine,
    replicas: Any,
) -> None:
    from fastapi.routing import APIRoute

    client, outsider, _ = replicas
    actor = login(client, "planning-owner:1")
    login(outsider, "planning-outsider:1")
    with Session(customer_engine) as db:
        wid = owned_workspace(db, actor)
    calls: list[str] = []

    def forbidden() -> None:
        calls.append("external dependency")
        raise AssertionError("execution runtime or media factory resolved before denial")

    for module, names in GUARDED:
        for c in (client, outsider):
            c.app.include_router(module.router)
        for route in module.router.routes:
            if not isinstance(route, APIRoute) or route.endpoint.__name__ not in names:
                continue
            for dependency in route.dependant.dependencies:
                call = dependency.call
                if call is not None and call.__name__.startswith("get_"):
                    # Do not replace actual authentication/DB dependencies.
                    if call.__module__.startswith(("app.customers", "app.database")):
                        continue
                    for c in (client, outsider):
                        c.app.dependency_overrides[call] = forbidden
            path = route.path_format.replace("{workspace_id}", str(wid))
            import re

            path = re.sub(r"\{[^}]+\}", "a" * 32, path)
            assert route.methods
            method = next(iter(route.methods))
            denied = client.request(method, path, headers=headers(client), json={})
            assert denied.status_code == 409, (path, denied.text)
            assert denied.json()["detail"] == "advertising_writes_disabled_in_planning_mvp"
            foreign = outsider.request(method, path, headers=headers(outsider), json={})
            assert foreign.status_code in {403, 404}, (path, foreign.text)
            if method != "GET":
                assert client.request(method, path, json={}).status_code == 403
    assert calls == []
