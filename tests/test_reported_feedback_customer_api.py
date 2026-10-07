"""Default-off customer surface remains owned, CSRF-bound and non-authorizing."""

from typing import Any

from app.api import customer_reported_feedback as api
from app.customers.models import CustomerMembership
from app.main import app
from app.workspaces.models import Workspace
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.reported_feedback_fixture import seeded
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import login
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers


def test_unavailable_api_is_owned_and_accepts_no_proof(
    replicas: Any,
    customer_engine: Engine,
) -> None:
    alice, bob, _ = replicas
    actor = login(alice, "alice:1")
    login(bob, "bob:1")
    for client in (alice, bob):
        client.app.include_router(api.router)
    with Session(customer_engine) as db:
        space = Workspace(slug="reported-alpha", name="Alpha", client_name="Alpha", status="active")
        db.add(space)
        db.flush()
        wid = space.id
        db.add(CustomerMembership(user_id=actor, workspace_id=wid, role="owner"))
        db.commit()
    root = f"/api/customer/v1/workspaces/{wid}/reported-feedback"
    response = alice.get(root + "/options")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert response.json()["comparison_available"] is False
    assert response.json()["preview_update_available"] is False
    assert response.json()["window_policy"] is None
    assert response.json()["actions"] == response.json()["baselines"] == []
    assert response.json()["review_available"] is False
    assert response.json()["spending_authority"] == "none"
    assert bob.get(root + "/options").status_code == 404
    intent = {
        "attempt_id": "a" * 32,
        "goal_id": "b" * 32,
        "goal_revision": 1,
        "maximum_reported_cpa_micros": 1000000,
    }
    assert alice.post(root + "/comparisons", json=intent).status_code == 403
    assert alice.post(root + "/comparisons", headers=headers(alice), json=intent).status_code == 503
    for proof in ("policy", "reported_cpa", "cohort", "spending_authority"):
        assert (
            alice.post(
                root + "/comparisons", headers=headers(alice), json={**intent, proof: {}}
            ).status_code
            == 422
        )
    assert (
        alice.post(
            root + "/previews",
            headers=headers(alice),
            json={
                "comparison_id": "a" * 32,
                "baseline_preview_id": "b" * 32,
            },
        ).status_code
        == 503
    )
    with Session(customer_engine) as db:
        member = db.get(CustomerMembership, (actor, wid))
        assert member
        member.role = "viewer"
        db.commit()
    assert alice.get(root + "/options").status_code == 403


def test_reported_comparison_shell_is_csp_protected() -> None:
    with TestClient(app) as client:
        result = client.get("/app/reported-comparison")
    assert result.status_code == 200
    assert result.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in result.headers["content-security-policy"]
    assert "Update Preview From This Comparison" in result.text
    assert "Review handoff is unavailable" in result.text
    assert "onclick=" not in result.text


def test_actual_owned_action_discovery_request_history_and_session_fence(
    replicas: Any,
    customer_engine: Engine,
    configuration: Any,
    tmp_path: Any,
) -> None:
    from app.customers.models import CustomerUser
    from app.reported_feedback.models import ReportedFeedbackJob
    from app.reported_feedback.runtime import get_reported_feedback_runtime

    alice, bob, _ = replicas
    with Session(customer_engine) as db:
        wid, principal, _, runtime, intent, original, _, server = seeded(
            db, configuration, tmp_path
        )
        user = db.get(CustomerUser, principal.user.id)
        assert user
        user.subject = "reported-api"
        db.commit()
    login(alice, "reported-api:first")
    for client in (alice, bob):
        client.app.include_router(api.router)
        client.app.dependency_overrides[get_reported_feedback_runtime] = lambda: runtime
    root = f"/api/customer/v1/workspaces/{wid}/reported-feedback"
    choice = alice.get(root + "/options")
    assert choice.status_code == 200, choice.text
    assert choice.json()["comparison_available"] is True
    assert choice.json()["preview_update_available"] is False
    assert len(choice.json()["actions"]) == 1
    action = choice.json()["actions"][0]
    assert action["id"] == intent.attempt_id and "Owned Campaign" in action["label"]
    assert choice.json()["baselines"] == []
    request = alice.post(
        root + "/comparisons", headers=headers(alice), json=intent.model_dump(mode="json")
    )
    assert request.status_code == 200, request.text
    value = request.json()
    assert value["completed_observations"] == 0 and value["required_observations"] == 4
    assert value["id"] != original.id
    repeated = alice.post(
        root + "/comparisons", headers=headers(alice), json=intent.model_dump(mode="json")
    )
    assert repeated.status_code == 200 and repeated.json()["id"] == value["id"]
    history = alice.get(root + "/comparisons")
    assert history.status_code == 200 and [v["id"] for v in history.json()] == [value["id"]]
    assert alice.get(root + f"/comparisons/{value['id']}/status").status_code == 200
    assert alice.get(root + f"/comparisons/{value['id']}").status_code == 409
    assert (
        alice.post(
            root + f"/comparisons/{value['id']}/reobserve", headers=headers(alice)
        ).status_code
        == 409
    )
    assert alice.get(root + "/previews/" + "0" * 32).status_code == 404
    login(bob, "reported-api:second")
    assert bob.get(root + f"/comparisons/{value['id']}/status").status_code == 404
    assert bob.get(root + "/comparisons").json() == []
    with Session(customer_engine) as db:
        assert db.get(ReportedFeedbackJob, value["id"]) is not None
    assert len(server.posts) == 1  # Only the original fixture action; reporting never mutates ads.


from tests.test_shopify_sales import configuration as configuration  # noqa: E402
