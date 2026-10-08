from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from app import advertising_capabilities
from app.api.customer_activity import REVISION_LIMIT, activity, router
from app.campaign_review.models import CampaignDraft, CampaignRevision
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.goals.models import Goal, GoalRevision
from app.publication import coordinator as c
from app.publication.execution_models import ProviderExecutionReceipt
from app.publication.provider_contracts import ProviderResponse
from app.settings import Settings
from app.workspaces.models import Workspace
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW as PROVIDER_NOW
from tests.test_customer_identity import (
    FakeProvider,
    login,
)
from tests.test_customer_identity import (
    customer_engine as customer_engine,
)
from tests.test_customer_identity import (
    replicas as replicas,
)
from tests.test_provider_coordinator import GoogleServer, ready
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary

NOW = datetime(2026, 10, 6, tzinfo=UTC)
PRIVATE = "private-payload-token@example.invalid"


def test_owned_bounded_persisted_history_and_revocation(
    replicas: tuple[TestClient, TestClient, FakeProvider], customer_engine: Engine
) -> None:
    client, other, _ = replicas
    assert isinstance(client.app, FastAPI) and isinstance(other.app, FastAPI)
    client.app.include_router(router)
    other.app.include_router(router)
    uid = login(client, "activity-owner:1")
    login(other, "activity-outsider:1")
    with Session(customer_engine) as db:
        w = Workspace(slug="activity", name="Activity", client_name="Activity", status="active")
        db.add(w)
        db.flush()
        wid = w.id
        db.add(CustomerMembership(user_id=uid, workspace_id=wid, role="owner"))
        db.add(Goal(id="g" * 32, workspace_id=wid, revision=REVISION_LIMIT + 2))
        db.add(CampaignDraft(id="c" * 32, workspace_id=wid, revision=1))
        db.flush()
        for revision in range(1, REVISION_LIMIT + 3):
            db.add(
                GoalRevision(
                    goal_id="g" * 32,
                    workspace_id=wid,
                    revision=revision,
                    definition={"private": PRIVATE},
                    editor_id=uid,
                    created_at=NOW,
                    confirmed_at=NOW + timedelta(seconds=revision) if revision == 1 else None,
                )
            )
        db.add(
            CampaignRevision(
                draft_id="c" * 32,
                workspace_id=wid,
                revision=1,
                artifact={"private": PRIVATE},
                digest="a" * 64,
                created_by=uid,
                created_at=NOW,
                approved_at=NOW + timedelta(seconds=5),
            )
        )
        db.commit()
    path = f"/api/customer/v1/workspaces/{wid}/activity"
    assert other.get(path).status_code == 404
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    result = response.json()
    assert result["truncated"] is True
    assert result["receipt_coverage"] == "latest_for_recent_attempts"
    assert len(result["items"]) == REVISION_LIMIT + 3
    assert result["items"][0]["event"] == "approved"
    assert result["items"][1]["event"] == "confirmed"
    saved = [
        r["revision"] for r in result["items"] if r["source"] == "goal" and r["event"] == "saved"
    ]
    assert saved == list(range(REVISION_LIMIT + 2, 2, -1))
    assert (
        PRIVATE not in response.text and uid not in response.text and "g" * 32 not in response.text
    )
    assert client.get(path).json() == result
    with Session(customer_engine) as db:
        member = db.scalar(select(CustomerMembership).where(CustomerMembership.user_id == uid))
        assert member
        member.role = "viewer"
        db.commit()
    assert client.get(path).json()["receipt_coverage"] == "owner_only"
    with Session(customer_engine) as db:
        member = db.scalar(select(CustomerMembership).where(CustomerMembership.user_id == uid))
        assert member
        member.status = "suspended"
        db.commit()
    assert client.get(path).status_code == 404
    with Session(customer_engine) as db:
        row = db.scalar(select(CustomerSession).where(CustomerSession.user_id == uid))
        assert row
        row.revoked_at = 1
        db.commit()
    assert client.get(path).status_code == 401


def test_latest_validated_provider_receipt_and_corruption(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = GoogleServer()
    server.timeout = True
    with Session(customer_engine) as db:
        with monkeypatch.context() as historical:
            historical.setattr(advertising_capabilities, "require_advertising_write", lambda: None)
            wid, run_id, actor, store, runtime = ready(db, configuration, tmp_path, server)
            claim = c.claim_creation_step(
                db, wid, run_id, actor, store, runtime, lambda: PROVIDER_NOW
            )
            assert claim
            c.execute_claim(db, claim, actor, store, runtime, lambda: PROVIDER_NOW)
        with pytest.raises(advertising_capabilities.AdvertisingWritesDisabled):
            advertising_capabilities.require_advertising_write()
        user = db.get(CustomerUser, actor)
        assert user
        principal = CustomerPrincipal(user, CustomerSession())
        view = activity(wid, principal, db, Response())
        receipts = [item for item in view.items if item.source == "provider_receipt"]
        assert len(receipts) == 1 and receipts[0].event == "unknown"
        assert receipts[0].environment == "contract_test"
        c.record_response(
            db,
            wid,
            claim.attempt_id,
            ProviderResponse(
                request_digest=claim.request.digest(),
                outcome="acknowledged",
                resource_name=next(iter(server.rows)),
            ),
            lambda: PROVIDER_NOW,
        )
        c.reconcile_attempt(db, wid, claim.attempt_id, runtime, lambda: PROVIDER_NOW)
        view = activity(wid, principal, db, Response())
        assert [r.event for r in view.items if r.source == "provider_receipt"] == [
            "verified_effect"
        ]
        assert "customers/" not in view.model_dump_json()
        latest = db.scalar(
            select(ProviderExecutionReceipt).order_by(ProviderExecutionReceipt.sequence.desc())
        )
        assert latest
        latest.projection = {"private": PRIVATE}
        db.commit()
        view = activity(wid, principal, db, Response())
        assert view.receipt_unavailable == 1
        assert not [r for r in view.items if r.source == "provider_receipt"]
        assert PRIVATE not in view.model_dump_json()
        assert server.posts == 1
