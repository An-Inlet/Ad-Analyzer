"""Bounded clock feasibility, not full frozen Q16 or browser acceptance."""

import time
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from app.api import customer as customer_api
from app.api import customer_planning_documents as api
from app.billing.entitlements import paid_work
from app.billing.service import checkout, reconcile
from app.billing.webhooks import receive
from app.commerce.sync import CommerceSyncService
from app.customers.access import SESSION_COOKIE, TTL_SECONDS, digest
from app.customers.identity import verified_identity
from app.customers.models import CustomerSession
from app.goals import service as goals
from app.goals.progress import read_goal_progress
from app.goals.schemas import ConfirmInput, GoalDefinition
from app.planning_documents.models import PlanRow
from app.publication.execution_models import ProviderExecutionAttempt
from app.settings import Settings, settings
from fastapi import HTTPException
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests import test_customer_billing as billing
from tests.test_commerce_measurement import FakeMeasurement, agreement, source, window
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import login
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_planning_documents_api import create_body
from tests.test_planning_evidence_adapter import setup_evidence
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary
NOV3 = datetime(2026, 11, 3, 5, 5, tzinfo=UTC)
NOV4 = datetime(2026, 11, 4, 5, 5, tzinfo=UTC)


def paid(
    engine: Engine,
    wid: int,
    now: datetime,
    monkeypatch: pytest.MonkeyPatch,
    *,
    initial: bool = True,
) -> None:
    # Only fixture-provider response time changes; production webhook/entitlement
    # validation and the actual subscription lifetime remain untouched.
    monkeypatch.setattr(billing, "NOW", now)
    fixture = billing.FixtureBilling()
    with Session(engine) as db:
        if initial:
            checkout(db, wid, billing.POLICY, fixture, "https://inlet.example/settings", now)
        body = billing.payload("evt_q16_" + str(int(now.timestamp())))
        identifier = "evt_q16_" + str(int(now.timestamp()))
        assert receive(db, body, billing.signature(body, now), billing.SECRET, now)
        assert reconcile(db, wid, identifier, billing.POLICY, fixture, now)
    monkeypatch.setattr(settings, "billing_required", True)
    monkeypatch.setattr(settings, "billing_price_id", billing.POLICY.price_id)
    monkeypatch.setattr(settings, "billing_max_accounts", 3)
    with Session(engine) as db:
        paid_work(db, wid, now)


def issue_at(alice: Any, provider: Any, subject: str, now: datetime) -> None:
    stamp = int(now.timestamp())
    project = provider.issuer.rsplit("/", 1)[1]
    real_time = time.time

    def verify(token: str) -> Any:
        assert token == f"q16-{stamp}"
        provider.check_active(subject, stamp)
        return verified_identity(
            dict(
                iss=provider.issuer,
                aud=project,
                sub=subject,
                email="same@example.test",
                email_verified=True,
                auth_time=stamp,
                iat=stamp,
                exp=stamp + 3600,
            ),
            project,
            stamp,
        )

    with pytest.MonkeyPatch.context() as issue:
        issue.setattr(customer_api, "time", SimpleNamespace(time=lambda: stamp))
        issue.setattr(provider, "verify", verify)
        login(alice, f"q16-{stamp}")
        assert time.time is real_time
    assert vars(customer_api)["time"] is time


def test_real_october_session_cannot_authorize_november_service_clock(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, ticket, principal, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "google_ads"
    )
    wid = ticket.inputs.workspace_id
    now = datetime.now(UTC)
    assert now < NOV3  # This fixed future-clock experiment has an explicit lifespan.
    original_session = (
        principal.session.created_at,
        principal.session.expires_at,
        principal.session.authenticated_at,
    )
    with Session(customer_engine) as db:
        reader = FakeMeasurement(
            configuration, [([source(updated=now - timedelta(seconds=2))], None)]
        )
        reader.facts = [agreement(gross="8000", tax="0")]
        # Existing setup already synced now; use the supported next scheduled stage,
        # without changing its persisted freshness timestamp or production cadence.
        confirmation_time = now + timedelta(minutes=configuration.shopify_sync_interval_minutes + 1)
        result = CommerceSyncService(db, configuration, reader).page(wid, now=confirmation_time)
        assert result["status"] == "complete", result
        goal = goals.owned(db, wid, ticket.inputs.goal.goal_id)
        definition = GoalDefinition.model_validate(goals.current(db, goal).definition)
        definition = GoalDefinition.model_validate(
            definition.model_copy(
                update={
                    "target_micros": 12_000_000_000,
                    "target_window": window(date(2026, 11, 1), date(2026, 12, 1)),
                    "deadline": date(2026, 11, 30),
                    "budget_micros": 1_000_000_000,
                    "budget_start": date(2026, 11, 1),
                    "budget_end": date(2026, 12, 1),
                }
            ).model_dump()
        )
        goals.revise(db, goal, definition, principal.user.id, confirmation_time)
        preview = goals.preview(db, goal, confirmation_time)
        goals.confirm(
            db,
            goal,
            ConfirmInput(
                expected_revision=goal.revision,
                preview_id=preview.id,
                idempotency_key="q16-confirm",
            ),
            confirmation_time,
            actor_id=principal.user.id,
        )
        confirmed_revision, confirmed_preview = goal.revision, goal.confirmed_preview_id
        db.commit()
    paid(customer_engine, wid, NOV3, monkeypatch)
    with Session(customer_engine) as db:
        reader = FakeMeasurement(
            configuration, [([source(updated=NOV3 - timedelta(seconds=2))], None)]
        )
        reader.facts = [agreement(gross="8000", tax="0")]
        assert (
            CommerceSyncService(db, configuration, reader).page(wid, now=NOV3)["status"]
            == "complete"
        )
    monkeypatch.setattr(api, "utc_now", lambda: NOV3)
    alice, _, _ = replicas
    alice.app.include_router(api.router)
    root = f"/api/customer/v1/workspaces/{wid}/planning/plans"
    body = create_body(ticket.inputs)
    body["inputs"]["goal_revision"] = confirmed_revision
    identity_check = alice.get("/api/customer/v1/session")
    assert identity_check.status_code == 200, identity_check.text
    with Session(customer_engine) as db:
        current = db.get(CustomerSession, principal.session.digest)
        assert current and current.revoked_at is None
        assert current.expires_at > datetime.now(UTC).timestamp()
    created = alice.post(root, headers=headers(alice), json=body)
    assert created.status_code == 401, created.text
    assert created.json()["detail"] == "customer authentication required"
    # This is the exact unsupported clock combination, not a passing Q16 journey.
    # No session expiry edit, auth override, or simulated successful generation.
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(PlanRow)) == 0
        goal = goals.owned(db, wid, ticket.inputs.goal.goal_id)
        assert (goal.revision, goal.confirmed_preview_id) == (confirmed_revision, confirmed_preview)
        assert goals.baseline(db, goal, definition, NOV3)["net_sales_micros"] == 8_000_000_000
        with pytest.raises(HTTPException) as rejected:
            read_goal_progress(
                db, principal, replicas[2], wid, goal.id, goal.revision, clock=lambda: NOV3
            )
        assert rejected.value.status_code == 401
    issue_at(alice, replicas[2], principal.user.subject, NOV3)
    with Session(customer_engine) as db:
        issued = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
        assert issued and issued.created_at == int(NOV3.timestamp())
        assert issued.expires_at - issued.created_at == TTL_SECONDS
    created = alice.post(root, headers=headers(alice), json=body)
    assert created.status_code == 201, created.text
    url = root + "/" + created.json()["plan_id"]
    generated = alice.post(
        url + "/generate",
        headers=headers(alice),
        json=dict(expected_input_revision=1, expected_version=0, request_key="q16-clock-generate"),
    )
    assert generated.status_code == 200, generated.text
    initial = alice.get(url + "/progress", params={"version": 1})
    assert initial.status_code == 200, initial.text
    assert initial.json()["net_sales_micros_exact"] == "0"
    original_digest = generated.json()["document_digest"]
    with Session(customer_engine) as db:
        reader = FakeMeasurement(
            configuration, [([source(updated=NOV4 - timedelta(seconds=2))], None)]
        )
        reader.facts = [
            agreement(gross="8000", tax="0"),
            agreement(2, "25", "0", when=NOV3 + timedelta(hours=10)),
        ]
        assert (
            CommerceSyncService(db, configuration, reader).page(wid, now=NOV4)["status"]
            == "complete"
        )
    paid(customer_engine, wid, NOV4, monkeypatch, initial=False)
    monkeypatch.setattr(api, "utc_now", lambda: NOV4)
    expired = alice.get(url + "/progress", params={"version": 1})
    assert expired.status_code == 401, expired.text
    issue_at(alice, replicas[2], principal.user.subject, NOV4)
    later = alice.get(url + "/progress", params={"version": 1})
    assert later.status_code == 200, later.text
    assert later.json()["net_sales_micros_exact"] == "25000000"
    assert later.json()["document_digest"] == original_digest
    assert (
        later.json()["sales"]["coverage"]["closed_day_count"]
        == initial.json()["sales"]["coverage"]["closed_day_count"] + 1
    )
    with Session(customer_engine) as db:
        current = db.get(CustomerSession, principal.session.digest)
        assert (
            current
            and (current.created_at, current.expires_at, current.authenticated_at)
            == original_session
        )
        issued = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
        assert issued and issued.expires_at - issued.created_at == TTL_SECONDS
        assert db.scalar(select(func.count()).select_from(PlanRow)) == 1
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
        goal = goals.owned(db, wid, ticket.inputs.goal.goal_id)
        assert (goal.revision, goal.confirmed_preview_id) == (confirmed_revision, confirmed_preview)
