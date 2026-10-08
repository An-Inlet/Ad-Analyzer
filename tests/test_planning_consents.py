"""Integrated planning confirmations cannot supply execution consent or authority."""

from pathlib import Path
from typing import Any

import pytest
from app.api.customer_initial_planning import get_initial_planning_runtime
from app.customers.access import SESSION_COOKIE, CustomerPrincipal, digest
from app.customers.models import CustomerSession, CustomerUser
from app.initial_planning.planning_consent_models import PlanningConsentRow
from app.initial_planning.planning_consents import checked_planning_limits
from app.publication.execution_models import ProviderExecutionConsent, ProviderExecutionMandate
from app.settings import Settings, settings
from fastapi import HTTPException
from sqlalchemy import Engine, event, func, select
from sqlalchemy.orm import Session

from tests.budget_mandate_fixture import first_customer
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import login
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def confirm(client: Any, root: str, body: Any) -> Any:
    prepared = client.post(root + "/budget-mandates", json=body, headers=headers(client))
    assert prepared.status_code == 201, prepared.text
    value = prepared.json()
    consent = {
        "selection": body["intent"]["selection"],
        "expected_revision": value["revision"],
        "policy_digest": value["policy_digest"],
        "preparation_digest": value["preparation_digest"],
    }
    url = root + "/budget-mandates/" + value["mandate_id"] + "/consent"
    response = client.post(url, json=consent, headers=headers(client))
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "confirmed"
    assert response.json()["planning_only"] and response.json()["spending_authority"] == "none"
    return value, url, consent


@pytest.mark.parametrize(
    "change", ["erasure", "profile", "policy", "source", "goal", "revision", "confirmer"]
)
def test_current_confirmation_fences(
    customer_engine: Engine,
    replicas: Any,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    from app.customers.models import CustomerMembership
    from app.meta.models import MetaConnection

    client, root, body, _, _, _, wid, _ = first_customer(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
    )
    value, _, _ = confirm(client, root, body)
    actor = login(client, "budget-first:2")  # Legitimate later session may use planning limits.
    confirmer = actor
    if change == "confirmer":
        actor = login(client, "planning-second-owner:1")
        with Session(customer_engine) as membership_db:
            membership_db.add(CustomerMembership(user_id=actor, workspace_id=wid, role="owner"))
            membership_db.commit()
    with Session(customer_engine) as db:
        user = db.get(CustomerUser, actor)
        session = db.get(CustomerSession, digest(client.cookies[SESSION_COOKIE]))
        assert user and session
        principal = CustomerPrincipal(user, session)
        runtime = get_initial_planning_runtime(db)
        policy = checked_planning_limits(
            db, principal, replicas[2], wid, value["mandate_id"], value["revision"], runtime
        )
        record = db.get(PlanningConsentRow, (value["mandate_id"], value["revision"]))
        assert record
        if change == "erasure":
            db.delete(record)
        elif change == "source":
            source = db.scalar(select(MetaConnection).where(MetaConnection.workspace_id == wid))
            assert source
            source.status = "reconnect_required"
        elif change == "goal":
            from app.goals.models import Goal

            goal = db.get(Goal, policy.goal_id)
            assert goal
            goal.revision += 1
        elif change == "revision":
            row = db.get(ProviderExecutionMandate, value["mandate_id"])
            assert row
            row.revision += 1
        elif change == "confirmer":
            member = db.get(CustomerMembership, (confirmer, wid))
            assert member
            member.status = "suspended"
        db.commit()
        if change == "profile":
            from dataclasses import replace

            runtime = replace(runtime, profile=None)
        elif change == "policy":
            monkeypatch.setattr(settings, "budget_mandate_policy_digest", "f" * 64)
        with pytest.raises(HTTPException) as rejected:
            checked_planning_limits(
                db, principal, replicas[2], wid, value["mandate_id"], value["revision"], runtime
            )
        assert rejected.value.status_code in {401, 403, 404, 409}
        assert db.scalar(select(func.count()).select_from(ProviderExecutionConsent)) == 0


def test_confirmation_insert_rollback_after_session_revocation(
    customer_engine: Engine,
    replicas: Any,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, root, body, _, _, _, wid, _ = first_customer(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
    )

    def revoke(*args: Any) -> None:
        replicas[2].revoked.add("budget-first")

    event.listen(PlanningConsentRow, "after_insert", revoke)
    try:
        with pytest.raises(AssertionError):
            confirm(client, root, body)
    finally:
        event.remove(PlanningConsentRow, "after_insert", revoke)
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(PlanningConsentRow)) == 0
        assert db.scalar(select(func.count()).select_from(ProviderExecutionConsent)) == 0
        assert db.scalar(select(ProviderExecutionMandate.state)) == "draft"
