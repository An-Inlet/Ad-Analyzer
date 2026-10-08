"""Actual owned status/default-off endpoints preserve immutable preview bytes."""

from typing import Any

import pytest
from app.api import customer_initial_planning as api
from app.customers.access import SESSION_COOKIE, CustomerPrincipal, digest
from app.customers.models import CustomerSession, CustomerUser
from app.initial_planning.models import PreviewRow
from app.publication.contracts import fingerprint
from app.publication.customer_optimization_contracts import get_customer_optimization_runtime
from app.publication.execution_models import ProviderExecutionApproval, ProviderExecutionAttempt
from app.settings import Settings
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine  # noqa: F401
from tests.test_customer_identity import login
from tests.test_customer_identity import replicas as replicas  # noqa: F401
from tests.test_customer_optimization_api import headers
from tests.test_initial_planning_api import ready_history
from tests.test_shopify_sales import configuration as configuration  # noqa: F401


@pytest.mark.planning_boundary
@pytest.mark.parametrize("configured", [False, True])
def test_owned_status_default_off_and_session_binding(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch,
    replicas: Any, configured: bool,
) -> None:
    alice, bob, provider = replicas
    actor = login(alice, "alice:1")
    with Session(customer_engine) as db:
        user = db.get(CustomerUser, actor)
        session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
        assert user and session
        wid, gid, _, _, runtime, observations = ready_history(
            customer_engine, configuration, monkeypatch, CustomerPrincipal(user, session), provider
        )
    for client in (alice, bob):
        client.app.include_router(api.router)
        client.app.dependency_overrides[api.get_initial_planning_runtime] = lambda: runtime
    root = f"/api/customer/v1/workspaces/{wid}/initial-planning"
    report = alice.post(
        root + "/calibrations",
        headers=headers(alice),
        json={
            "observation_id": observations[-1],
            "goal_id": gid,
            "goal_revision": 1,
            "maximum_reported_cpa_micros": 10000000,
        },
    )
    assert report.status_code == 200, report.text
    result = alice.post(
        root + "/previews",
        headers=headers(alice),
        json={
            "calibration_id": report.json()["id"],
            "observation_id": observations[-1],
        },
    )
    assert result.status_code == 200, result.text
    document = result.json()
    path = root + "/previews/" + document["id"]
    status = alice.get(path + "/review-status")
    assert status.status_code == 200, status.text
    assert status.headers["cache-control"] == "no-store"
    value = status.json()
    assert value == {
        "preview_id": document["id"],
        "preview_digest": fingerprint(document["schema_version"], document),
        "request_available": False,
        "reason": "review_service_unavailable",
        "financial_qualification": "not_checked",
        "spending_authority": "none",
    }
    if configured:
        def forbidden_runtime() -> None:
            raise AssertionError("Current review must deny before legacy runtime construction")

        alice.app.dependency_overrides[get_customer_optimization_runtime] = forbidden_runtime
    body = {"expected_preview_digest": value["preview_digest"]}
    assert alice.post(path + "/review", json=body).status_code == 403
    for intent in (body, {**body, "amount_micros": 1}):
        denied = alice.post(path + "/review", headers=headers(alice), json=intent)
        assert denied.status_code == 409
        assert denied.json()["detail"] == "advertising_writes_disabled_in_planning_mvp"
    alice.app.dependency_overrides.pop(get_customer_optimization_runtime, None)
    login(bob, "alice:second")
    assert bob.get(path + "/review-status").status_code == 409
    assert bob.post(path + "/review", headers=headers(bob), json=body).status_code == 409
    assert alice.get(path).json() == document
    with Session(customer_engine) as db:
        row = db.get(PreviewRow, document["id"])
        assert row and row.document == document and document["review_available"] is False
        assert db.scalar(select(func.count()).select_from(ProviderExecutionApproval)) == 0
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0


def historical_contract_configured_review_uses_owned_digest_and_never_approves(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch, replicas: Any
) -> None:
    from dataclasses import replace

    from app.api.customer_execution import router as execution_router
    from app.initial_planning.invalidation import erase_workspace_observations
    from app.publication.execution_models import ProviderExecutionReview

    from tests.test_initial_preview_review import ready

    wid, document, _, _, bridge, server, calls = ready(
        customer_engine, configuration, monkeypatch, replicas
    )
    alice, _, _ = replicas
    planning = replace(bridge.planning, native=bridge.optimization)
    alice.app.dependency_overrides[api.get_initial_planning_runtime] = lambda: planning
    alice.app.dependency_overrides[get_customer_optimization_runtime] = lambda: bridge.optimization
    alice.app.include_router(execution_router)
    path = f"/api/customer/v1/workspaces/{wid}/initial-planning/previews/{document.id}"
    status = alice.get(path + "/review-status")
    assert status.status_code == 200, status.text
    assert status.json()["request_available"] is True
    assert status.json()["financial_qualification"] == "not_checked"
    assert not calls
    unavailable = replace(planning, native=replace(bridge.optimization, initial_planning=None))
    alice.app.dependency_overrides[get_customer_optimization_runtime] = lambda: unavailable.native
    absent = alice.get(path + "/review-status")
    assert absent.status_code == 200 and not absent.json()["request_available"]
    assert (
        alice.post(
            path + "/review",
            headers=headers(alice),
            json={
                "expected_preview_digest": status.json()["preview_digest"],
            },
        ).status_code
        == 503
    )
    assert not calls
    assert planning.configuration is not None
    changed_policy = planning.configuration.model_copy(
        update={
            "preview_lifetime_seconds": planning.configuration.preview_lifetime_seconds + 1,
        }
    )
    changed = replace(
        bridge.optimization,
        initial_planning=replace(
            planning,
            configuration=changed_policy,
        ),
    )
    alice.app.dependency_overrides[get_customer_optimization_runtime] = lambda: changed
    assert not alice.get(path + "/review-status").json()["request_available"]
    assert (
        alice.post(
            path + "/review",
            headers=headers(alice),
            json={
                "expected_preview_digest": status.json()["preview_digest"],
            },
        ).status_code
        == 503
    )
    assert not calls
    alice.app.dependency_overrides[get_customer_optimization_runtime] = lambda: bridge.optimization
    wrong = alice.post(
        path + "/review",
        headers=headers(alice),
        json={
            "expected_preview_digest": "0" * 64,
        },
    )
    assert wrong.status_code == 409 and not calls
    body = {"expected_preview_digest": status.json()["preview_digest"]}
    result = alice.post(path + "/review", headers=headers(alice), json=body)
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "review_required"
    assert result.json()["spending_authority"] == "none"
    assert calls == ["qualification", "exposure"] and not server.posts
    replay = alice.post(path + "/review", headers=headers(alice), json=body)
    assert replay.status_code == 200 and replay.json() == result.json()
    assert calls == ["qualification", "exposure"]
    owned = alice.get(
        f"/api/customer/v1/workspaces/{wid}/execution/reviews/{result.json()['review_id']}"
    )
    assert (
        owned.status_code == 200 and owned.json()["review_digest"] == result.json()["review_digest"]
    )
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderExecutionReview)) == 1
        assert db.scalar(select(func.count()).select_from(ProviderExecutionApproval)) == 0
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
        erase_workspace_observations(db, wid)
        db.commit()
    assert alice.get(path + "/review-status").status_code == 404
    assert alice.post(path + "/review", headers=headers(alice), json=body).status_code == 404
    with Session(customer_engine) as db:
        assert db.get(ProviderExecutionReview, result.json()["review_id"]) is not None
