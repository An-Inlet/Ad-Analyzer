"""Canonical local-day boundaries and owned current planning context."""

from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from app.api import customer_plan_review as api
from app.customers.models import CustomerUser
from app.database.session import get_db
from app.google_connections.models import GoogleCustomerConnection
from app.publication import execution_mandates
from app.settings import Settings
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.candidate_current_fixture import current_candidate_read as current_candidate_read
from tests.candidate_read_retained_fixture import CandidateReadIds
from tests.test_customer_goals import definition
from tests.test_customer_identity import ISSUER, FakeProvider, login
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_inlet_customer_journey import JourneyClock
from tests.test_shopify_sales import configuration as configuration


def test_period_uses_store_dst_and_rejects_ambiguous_midnight() -> None:
    value = definition("a" * 32)
    changed = value.model_copy(
        update={
            "target_window": value.target_window.model_copy(
                update={"time_zone": "America/New_York"}
            ),
            "budget_start": date(2026, 3, 8),
            "budget_end": date(2026, 3, 9),
        }
    )
    assert api.exact_period(changed) == (
        datetime(2026, 3, 8, 5, tzinfo=UTC),
        datetime(2026, 3, 9, 4, tzinfo=UTC),
    )
    for zone, day in [("America/Havana", date(2026, 11, 1)), ("Pacific/Apia", date(2011, 12, 30))]:
        changed = value.model_copy(
            update={
                "target_window": value.target_window.model_copy(update={"time_zone": zone}),
                "budget_start": day,
            }
        )
        with pytest.raises(HTTPException) as error:
            api.exact_period(changed)
        assert error.value.status_code == 422


@pytest.mark.planning_boundary
@pytest.mark.parametrize("change", [None, "goal", "source", "session"])
def test_current_owned_planning_context(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    change: str | None,
    current_candidate_read: tuple[Engine, CandidateReadIds],
) -> None:
    customer_engine, ids = current_candidate_read
    wid, actor = ids.workspace_id, ids.actor_id

    def database() -> Iterator[Session]:
        with Session(customer_engine) as current:
            yield current

    for client in replicas[:2]:
        client.app.dependency_overrides[get_db] = database  # type: ignore[attr-defined]
    with Session(customer_engine) as db:
        _, mandate = execution_mandates.owned(db, wid, ids.mandate_id)
        policy = execution_mandates.policy(db, mandate)
        assert mandate.revision == ids.mandate_revision and policy.digest() == ids.policy_digest
        assert len(policy.accounts) == 1
        scope = policy.accounts[0]
        assert scope.account.account_id == ids.account_id
        user = db.get(CustomerUser, actor)
        assert user
        user.issuer, user.subject = ISSUER, "planning-owner"
        db.commit()
    alice, bob, _ = replicas
    for client in (alice, bob):
        client.app.include_router(api.router)  # type: ignore[attr-defined]
    monkeypatch.setattr(api, "datetime", JourneyClock)
    login(alice, "planning-owner:1")
    login(bob, "other:1")
    path = f"/api/customer/v1/workspaces/{wid}/mandates/planning-context"
    payload: dict[str, Any] = dict(
        goal_id=policy.goal_id,
        expected_revision=policy.goal_revision,
        account_id=scope.account.account_id,
    )
    assert alice.post(path, json=payload).status_code == 403
    assert bob.post(path, json=payload, headers=headers(bob)).status_code == 404
    if change == "goal":
        payload["expected_revision"] += 1
    if change == "source":
        with Session(customer_engine) as db:
            row = db.scalar(
                select(GoogleCustomerConnection).where(
                    GoogleCustomerConnection.account_id == scope.account.account_id
                )
            )
            assert row
            row.status = "disconnected"
            db.commit()
    if change == "session":
        assert alice.delete("/api/customer/v1/session", headers=headers(alice)).status_code == 204
    response = alice.post(path, json=payload, headers=headers(alice))
    if change:
        assert response.status_code in {401, 403, 409}, response.text
    else:
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["mode"] == "simulation" and result["live_execution_enabled"] is False
        assert result["account"]["account_id"] == scope.account.account_id
        assert result["local_start"] == "2026-11-01" and result["total_ceiling_micros"] > 0
        assert "external_advertiser_id" not in response.text
        assert response.headers["cache-control"] == "no-store"
