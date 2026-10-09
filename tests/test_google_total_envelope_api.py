"""Actual configured creation/capture and native diagnostic wire, never financial proof."""

import base64
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.api import customer_account_diagnostics as api
from app.collectors import account_diagnostics
from app.customers.access import SESSION_COOKIE, digest
from app.customers.models import CustomerSession, CustomerUser
from app.database.session import get_db
from app.google_connections.models import GoogleCustomerConnection
from app.publication.execution_models import ProviderExecutionAttempt, ProviderExposureReservation
from app.settings import Settings, settings
from pydantic import SecretStr
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.google_created_retained_fixture import GoogleCreatedIds, graph, retained_google_created
from tests.google_runtime_fixture import configured_customer
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import login
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration


def created(
    engine: Engine, config: Settings, path: Path, monkeypatch: pytest.MonkeyPatch, replicas: Any
) -> Any:
    alice, base, body, draft, revision, server, requests, control = configured_customer(
        engine, config, path, monkeypatch, replicas, total_budget=True
    )
    alice.app.include_router(api.router)

    def post(route: str, data: Any = None, expected: int = 200) -> Any:
        result = alice.post(base + route, json=data, headers=headers(alice))
        assert result.status_code == expected, result.text
        return result.json()

    policy = post("/mandates", body, 201)
    post(
        f"/mandates/{policy['id']}/consent",
        {"expected_revision": policy["revision"], "policy_digest": policy["policy_digest"]},
    )
    catalog = post("/configuration-options", {"draft_id": draft})
    review = post(
        "/creation-reviews",
        {
            "draft_id": draft,
            "draft_revision": revision,
            "mandate_id": policy["id"],
            "mandate_revision": policy["revision"],
            "google": {
                "catalog_option_id": catalog["options"][0]["id"],
                "budget_kind": "campaign_total_v1",
                "total_budget_micros": 30,
                "max_cpc_micros": 1,
                "search_partners": False,
            },
        },
        201,
    )
    post(
        f"/reviews/{review['id']}/approval",
        {"review_digest": review["review_digest"], "plan_digest": review["plan_digest"]},
    )
    run = post(f"/reviews/{review['id']}/runs", expected=201)
    for _ in range(2):
        post(f"/runs/{run['id']}/advance")
    return alice, base, run, server


@pytest.mark.planning_boundary
@pytest.mark.parametrize(
    "change",
    [
        None,
        "lower",
        "disabled",
        "session",
        "generation",
        "csrf",
        "foreign",
        "late_expiry",
        "shared",
        "unknown",
    ],
)
def test_actual_created_total_envelope_read(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    change: str | None,
) -> None:
    with retained_google_created(
        customer_engine,
        tmp_path / "original",
        "total_created",
        expected_unknown=change == "unknown",
    ) as (engine, ids):

        def database() -> Any:
            with Session(engine) as db:
                yield db

        for client in replicas[:2]:
            client.app.dependency_overrides[get_db] = database
        alice = replicas[0]
        alice.app.include_router(api.router)
        with Session(engine) as db:
            actor = db.get(CustomerUser, ids.actor_id)
            assert actor
            identity = (actor.issuer, actor.subject)
            sessions = set(db.scalars(select(CustomerSession.digest)))
        assert login(alice, "configured-google:current-total") == ids.actor_id
        assert digest(alice.cookies[SESSION_COOKIE]) not in sessions
        with Session(engine) as db:
            actor = db.get(CustomerUser, ids.actor_id)
            assert actor and (actor.issuer, actor.subject) == identity
        monkeypatch.setattr(settings, "google_customer_client_id", "offline-client")
        monkeypatch.setattr(settings, "google_customer_client_secret", SecretStr("offline-secret"))
        monkeypatch.setattr(
            settings,
            "google_customer_encryption_key",
            SecretStr(base64.urlsafe_b64encode(b"g" * 32).decode()),
        )
        current_envelope_body(engine, monkeypatch, alice, ids, change)


def current_envelope_body(
    customer_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    alice: Any,
    ids: GoogleCreatedIds,
    change: str | None,
) -> None:
    base = f"/api/customer/v1/workspaces/{ids.workspace_id}/execution"
    run = {"id": ids.run_id}
    monkeypatch.setattr(settings, "customer_native_diagnostics_enabled", change != "disabled")
    calls = []
    with Session(customer_engine) as db:
        attempts = list(db.scalars(select(ProviderExecutionAttempt)))
        campaign = next(a.request for a in attempts if a.step_id == "campaign")
        scope = campaign["scope"]
        operation = campaign["step"]["operation"]
        budget_resource = campaign["resources"]["budget"]
        campaign_resource = ids.attempts[1].resource_name
        assert campaign_resource and "/campaigns/" in campaign_resource
        before = [
            (r.id, r.state, r.amount_micros)
            for r in db.scalars(select(ProviderExposureReservation))
        ]
    writes = ids.provider_posts
    if change == "unknown":
        from app.publication import coordinator
        from app.publication.provider_contracts import BoundProviderRequest

        with Session(customer_engine) as db:
            original = next(
                a for a in db.scalars(select(ProviderExecutionAttempt)) if a.step_id == "budget"
            )
            request = BoundProviderRequest.model_validate(original.request)
            coordinator.record_receipt(
                db,
                original.workspace_id,
                original.id,
                coordinator.unknown(request, request.dispatched_at),
                lambda: request.dispatched_at,
            )
            db.commit()

    # The intentional unknown receipt is complete; the HTTP read may change nothing further.
    before_http = graph(customer_engine)

    def wire(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert (request.url.host, request.url.path) == ("oauth2.googleapis.com", "/token") or (
            request.url.host == "googleads.googleapis.com"
            and request.url.path.endswith("/googleAds:search")
        )
        calls.append(request.url.path)
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(
                200,
                json={"access_token": "offline-read", "expires_in": 3600, "token_type": "Bearer"},
            )
        body = json.loads(request.content)
        query = body["query"]
        advertiser = scope["external_advertiser_id"]
        if "FROM customer" in query:
            if change in {"session", "generation"}:
                with Session(customer_engine) as db:
                    if change == "session":
                        session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
                        assert session
                        session.revoked_at = int(time.time())
                    else:
                        native = db.scalar(select(GoogleCustomerConnection))
                        assert native
                        native.generation += 1
                    db.commit()
            rows = [
                {
                    "customer": {
                        "id": advertiser,
                        "resourceName": f"customers/{advertiser}",
                        "currencyCode": "USD",
                        "timeZone": "Pacific/Pago_Pago",
                        "status": "ENABLED",
                    }
                }
            ]
        elif "FROM campaign_budget" in query:
            rows = [
                {
                    "campaignBudget": {
                        "resourceName": budget_resource,
                        "totalAmountMicros": "20" if change == "lower" else "30",
                        "referenceCount": "2" if change == "shared" else "1",
                        "period": "CUSTOM_PERIOD",
                        "status": "ENABLED",
                        "type": "STANDARD",
                    }
                }
            ]
        elif "metrics.cost_micros" in query:
            rows = []
        elif "FROM campaign " in query:
            rows = [
                {
                    "campaign": {
                        "resourceName": campaign_resource,
                        "campaignBudget": budget_resource,
                        "status": "PAUSED",
                        "advertisingChannelType": "SEARCH",
                        "biddingStrategyType": "MANUAL_CPC",
                        "startDateTime": operation["starts_local"],
                        "endDateTime": operation["ends_local"],
                    }
                }
            ]
        else:
            rows = []
        return httpx.Response(200, json={"results": rows})

    clock = [datetime.now(UTC)]
    monkeypatch.setattr(api, "utc_now", lambda: clock[0])

    class Transport(httpx.MockTransport):
        def close(self) -> None:
            if change == "late_expiry":
                clock[0] += timedelta(hours=1)
            super().close()

    monkeypatch.setattr(account_diagnostics, "diagnostic_transport", lambda: Transport(wire))
    selected = "f" * 32 if change == "foreign" else run["id"]
    result = alice.post(
        base + f"/runs/{selected}/envelope-observation",
        headers={} if change == "csrf" else headers(alice),
    )
    expected = {
        "disabled": 503,
        "session": 401,
        "generation": 409,
        "csrf": 403,
        "foreign": 404,
        "late_expiry": 409,
        "unknown": 409,
    }.get(change or "", 200)
    assert result.status_code == expected, result.text
    if change in {"disabled", "csrf", "foreign", "unknown"}:
        assert calls == []
    elif expected == 200:
        data = result.json()
        assert data["status"] == (
            "unavailable"
            if change == "shared"
            else "configuration_drift"
            if change == "lower"
            else "matching_configuration"
        )
        assert data["original_total_micros"] == 30
        assert data["observed_total_micros"] == (20 if change == "lower" else 30)
        assert data["financial_upper_micros"] is None
        assert data["spending_authority"] == "none"
        assert datetime.fromisoformat(data["observed_at"]) < datetime.fromisoformat(
            data["expires_at"]
        )
        assert calls
    assert (
        ids.provider_posts == writes == 2
    )  # Measured historical source; no current mutation HTTP.
    assert graph(customer_engine) == before_http
    with Session(customer_engine) as db:
        assert [
            (r.id, r.state, r.amount_micros)
            for r in db.scalars(select(ProviderExposureReservation))
        ] == before
