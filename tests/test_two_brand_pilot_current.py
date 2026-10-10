"""Two unrelated brands on one database; explicit offline bootstrap boundaries."""

from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from app.api.customer_execution import get_execution_media_factory
from app.campaign_review.storage import LocalMediaStore, get_media_store
from app.customer_context.http import HubSpotHTTPRead, KlaviyoHTTPRead
from app.customers.access import CSRF_COOKIE
from app.customers.identity import get_identity_provider
from app.database.session import get_db
from app.main import app
from app.publication import activation as activation
from app.publication import activation_review as activation_review
from app.publication import coordinator as coordinator
from app.settings import Settings, settings
from app.sources.contracts import get_source_transport
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_crm_http_runtime import CLIENT, SECRET, ProviderHTTP
from tests.test_customer_goals import definition
from tests.test_customer_identity import ORIGIN, FakeProvider, login
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_provisioning import signup
from tests.test_inlet_customer_journey import install_fixture_baseline
from tests.test_shopify_sales import configuration as configuration
from tests.test_tiktok_sources import configured as configured
from tests.test_two_brand_pilot import native_fixture, ok
from tests.two_brand_planning_inputs import bootstrap_reporting, install_native_wire


def test_two_brand_current_onboarding_planning_and_isolation(
    customer_engine: Engine,
    configuration: Settings,
    configured: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> None:
    monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)
    monkeypatch.setattr(settings, "billing_required", False)
    calls = install_native_wire(monkeypatch)
    identity = FakeProvider()
    media = LocalMediaStore(tmp_path)
    http = {p: ProviderHTTP(p) for p in ("klaviyo", "hubspot")}
    transports = {
        p: (KlaviyoHTTPRead if p == "klaviyo" else HubSpotHTTPRead)(
            CLIENT, SECRET, transport=httpx.MockTransport(io), clock=lambda: datetime.now(UTC)
        )
        for p, io in http.items()
    }

    def database() -> Generator[Session, None, None]:
        with Session(customer_engine) as db:
            yield db

    def source_transport(provider: str) -> Any:
        return transports[provider]

    monkeypatch.setattr(
        app,
        "dependency_overrides",
        {
            get_db: database,
            get_identity_provider: lambda: identity,
            get_media_store: lambda: media,
            get_execution_media_factory: lambda: lambda: media,
            get_source_transport: source_transport,
        },
    )
    clients = [TestClient(app, base_url=ORIGIN), TestClient(app, base_url=ORIGIN)]
    for client in clients:
        request.addfinalizer(client.close)
    brands: list[dict[str, Any]] = []
    for i, (client, crm, platform, external) in enumerate(
        zip(
            clients,
            ("klaviyo", "hubspot"),
            ("google_ads", "meta_ads"),
            ("1234567890", "123"),
            strict=True,
        )
    ):
        actor = login(client, f"pilot-owner-{i}:1")
        wid = ok(signup(client, f"pilot-signup-key-0000-{i}", f"pilot-brand-{i}"), 201)["id"]
        root = f"/api/customer/v1/workspaces/{wid}"
        headers = {"Origin": ORIGIN, "X-CSRF-Token": client.cookies[CSRF_COOKIE]}
        # Each toolchain starts with the supported CRM it already uses.
        start = ok(client.post(root + f"/sources/{crm}/authorize", headers=headers))
        state = parse_qs(urlsplit(start["authorization_url"]).query)["state"][0]
        if i:
            before = len(http[crm].calls)
            assert (
                clients[0]
                .post(
                    f"/api/customer/v1/sources/{crm}/callback",
                    headers=brands[0]["headers"],
                    json={"state": state, "code": "offline-code"},
                )
                .status_code
                == 404
            )
            assert len(http[crm].calls) == before
        ok(
            client.post(
                f"/api/customer/v1/sources/{crm}/callback",
                headers=headers,
                json={"state": state, "code": "offline-code"},
            )
        )
        connection = ok(
            client.post(
                root + f"/sources/{crm}/select",
                headers=headers,
                json={"state": state, "external_id": http[crm].account},
            )
        )
        with Session(customer_engine) as db:
            store = install_fixture_baseline(
                db, wid, configuration, shop=f"pilot-{i}.myshopify.com", shop_id=str(100 + i)
            )
            scope = native_fixture(db, wid, platform, external)
            # Original pilot boundary is an explicitly installed baseline, not
            # a real import. Its freshness must match the current API wallclock.

            from app.commerce.models import CommerceStore

            retained_store = db.get(CommerceStore, store)
            assert retained_store is not None
            retained_store.last_sync_at = datetime.now(UTC)
            db.commit()
        goal = ok(
            client.post(
                root + "/goals",
                headers={**headers, "Idempotency-Key": f"pilot-goal-{i}"},
                json={"definition": definition(store).model_dump(mode="json")},
            ),
            201,
        )
        gp = root + "/goals/" + goal["id"]
        preview = ok(client.post(gp + "/preview", headers=headers, json={"expected_revision": 1}))
        confirmed = ok(
            client.post(
                gp + "/confirm",
                headers=headers,
                json={
                    "expected_revision": 1,
                    "preview_id": preview["preview_id"],
                    "idempotency_key": f"pilot-confirm-{i}",
                },
            )
        )
        assert confirmed["assessment"] == "confirmed" and confirmed["spending_authorized"] is False
        with Session(customer_engine) as db:
            window = bootstrap_reporting(db, wid, scope)
        plans = root + "/planning/plans"
        created = ok(
            client.post(
                plans,
                headers=headers,
                json={
                    "request_key": f"pilot-plan-create-{i}",
                    "inputs": {
                        "goal_id": goal["id"],
                        "goal_revision": 1,
                        "account_ids": [scope.account_id],
                        "reporting_window": window,
                        "comparison_window": None,
                        "milestone": "Grow Shopify sales",
                        "product_offer": "Reusable bottle",
                        "constraints": [],
                        "assumptions": [],
                        "exclusions": [],
                        "fixed_allocations": [],
                        "scenario_intents": [],
                        "maximum_creative_assets": 1,
                    },
                },
            ),
            201,
        )
        plan = plans + "/" + created["plan_id"]
        generated = ok(
            client.post(
                plan + "/generate",
                headers=headers,
                json={
                    "expected_input_revision": 1,
                    "expected_version": 0,
                    "request_key": f"pilot-plan-generate-{i}",
                },
            )
        )
        value = ok(client.get(plan))
        assert value["freshness"] == "current"
        assert value["document"]["schema_version"] == "inlet.plan-version.v1"
        assert value["document"]["policy_version"] == "inlet.descriptive-review.v3"
        assert value["document"]["generator_version"] == "inlet.descriptive-planning.v3"
        assert value["document"]["inputs"]["goal"]["goal_id"] == goal["id"]
        assert [a["account_id"] for a in value["document"]["inputs"]["accounts"]] == [
            scope.account_id
        ]
        assert value["document_digest"] == generated["document_digest"]
        action = value["document"]["actions"][0]
        decision = dict(
            expected_version=1,
            expected_event_sequence=0,
            document_digest=value["document_digest"],
            action_key=action["key"],
            action_digest=value["action_digests"][action["key"]],
            decision="accepted_for_manual_application",
            reason="Reviewed offline plan",
            supersedes_event_id=None,
            request_key=f"pilot-plan-accept-{i}",
        )
        assert (
            ok(client.post(plan + "/decisions", headers=headers, json=decision))["event_sequence"]
            == 1
        )
        assert len(ok(client.get(plan + "/events"))["items"]) == 1
        assert (
            ok(client.get(plan + "/export?version=1"))["document_digest"]
            == value["document_digest"]
        )
        brands.append(
            dict(
                actor=actor,
                wid=wid,
                root=root,
                headers=headers,
                scope=scope,
                goal=goal["id"],
                plan=plan,
                decision=decision,
                crm=crm,
                connection=connection,
            )
        )
    a, b = brands
    assert a["wid"] != b["wid"] and a["actor"] != b["actor"]
    assert a["scope"].account_id != b["scope"].account_id
    assert a["scope"].connection_id != b["scope"].connection_id
    for own, foreign, client in ((a, b, clients[0]), (b, a, clients[1])):
        for suffix in ("/goals/" + foreign["goal"], "/sources/" + foreign["crm"], "/activity"):
            assert client.get(foreign["root"] + suffix).status_code == 404
        assert client.get(own["root"] + "/goals/" + foreign["goal"]).status_code == 404
        for suffix in ("", "/versions/1", "/events", "/export?version=1"):
            assert client.get(foreign["plan"] + suffix).status_code == 404
        assert (
            client.post(
                foreign["plan"] + "/decisions", headers=own["headers"], json=foreign["decision"]
            ).status_code
            == 404
        )
    before = len(calls)

    from app.customers.access import SESSION_COOKIE, digest
    from app.customers.models import CustomerSession
    from app.database.session import Base
    from sqlalchemy import func

    with Session(customer_engine) as db:
        session = db.get(CustomerSession, digest(clients[0].cookies[SESSION_COOKIE]))
        assert session is not None
        session.revoked_at = int(datetime.now(UTC).timestamp())
        db.commit()
    assert clients[0].get(a["plan"]).status_code == 401
    assert (
        clients[0]
        .post(a["plan"] + "/decisions", headers=a["headers"], json=a["decision"])
        .status_code
        == 401
    )
    assert len(calls) == before
    assert clients[1].get(b["plan"]).status_code == 200
    assert clients[1].get(b["root"] + "/goals/" + b["goal"]).status_code == 200
    assert clients[1].get(b["root"] + "/sources/hubspot").status_code == 200
    assert login(clients[0], "pilot-owner-0:current-recovery") == a["actor"]
    assert clients[0].get(a["plan"]).status_code == 200
    with Session(customer_engine) as db:
        for table in Base.metadata.tables.values():
            if table.name.startswith("provider_") or table.name in {
                "spending_mandates",
                "mandate_actions",
            }:
                assert db.scalar(select(func.count()).select_from(table)) == 0, table.name
    assert calls
