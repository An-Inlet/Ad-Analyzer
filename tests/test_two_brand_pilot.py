"""Two unrelated brands on one database; explicit offline bootstrap boundaries."""

from collections.abc import Generator
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount
from app.api import customer_campaign_review, customer_goals, customer_mandates, customer_sources
from app.api.customer_execution import get_execution_media_factory
from app.campaign_review.storage import LocalMediaStore, get_media_store
from app.commerce import reporting
from app.customers.access import CSRF_COOKIE
from app.customers.identity import get_identity_provider
from app.database.session import get_db
from app.goals import service as goals
from app.google_connections.models import GoogleCustomerConnection
from app.main import app
from app.mandates.schemas import AccountScope, MandateDefinition
from app.meta.models import MetaConnection
from app.publication import activation as activation
from app.publication import activation_review as activation_review
from app.publication import coordinator as coordinator
from app.publication.execution_contracts import ExecutionAccount, ProviderMandatePolicy
from app.publication.execution_models import ProviderExecutionAttempt, ProviderExposureReservation
from app.settings import Settings, settings
from app.sources.contracts import get_source_transport
from app.workspaces.models import WorkspaceIntegration
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests import test_provider_coordinator as creation_fixture
from tests.test_activation_coordinator import runtime_for
from tests.test_activation_review import activation_ready
from tests.test_campaign_review import definition as campaign_definition
from tests.test_campaign_review import png
from tests.test_commerce_measurement import NOW
from tests.test_crm_http_runtime import ProviderHTTP, adapter
from tests.test_customer_goals import definition
from tests.test_customer_identity import ORIGIN, FakeProvider, login
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_provisioning import signup
from tests.test_google_activation import Server
from tests.test_inlet_customer_journey import JourneyClock, install_fixture_baseline
from tests.test_shopify_sales import configuration as configuration
from tests.test_social_publication_http import reviewed
from tests.test_tiktok_sources import configured as configured


def ok(response: Any, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()


def native_fixture(db: Session, wid: int, platform: str, external: str) -> AccountScope:
    """Preauthorized ad-account bootstrap, not an OAuth qualification claim."""
    integration = WorkspaceIntegration(
        workspace_id=wid,
        integration_key="pilot-" + platform,
        provider=platform,
        display_name="Offline pilot",
        status="active",
        configuration={},
    )
    db.add(integration)
    db.flush()
    account = AdvertisingAccount(
        workspace_id=wid,
        connection_id=integration.id,
        platform=AdvertisingPlatform(platform),
        external_account_id=external,
        name="Offline pilot",
        currency_code="USD",
        time_zone="UTC",
    )
    db.add(account)
    db.flush()
    if platform == "google_ads":
        db.add(
            GoogleCustomerConnection(
                id=uuid4().hex,
                workspace_id=wid,
                integration_id=integration.id,
                account_id=account.id,
                external_account_id=external,
                encrypted_grant="fixture-unopened",
                generation=1,
                window_start=NOW.date(),
                window_end=NOW.date(),
                backfill_through=NOW.date(),
                history_floor=NOW.date(),
                phase="recent",
                staged={},
            )
        )
    else:
        db.add(
            MetaConnection(
                workspace_id=wid,
                workspace_integration_id=integration.id,
                account_id=account.id,
                external_account_id=external,
                encrypted_credentials="fixture-unopened",
            )
        )
    db.commit()
    return AccountScope(account_id=account.id, connection_id=integration.id, platform=platform)


def retained_test_two_brands_api_review_execution_and_closure_isolation(
    customer_engine: Engine,
    configuration: Settings,
    configured: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    for module in (
        customer_goals,
        customer_mandates,
        customer_campaign_review,
        customer_sources,
        goals,
        reporting,
    ):
        monkeypatch.setattr(module, "datetime", JourneyClock)
    monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)
    monkeypatch.setattr(settings, "billing_required", False)
    identity = FakeProvider()
    media = LocalMediaStore(tmp_path)
    http = {p: ProviderHTTP(p) for p in ("klaviyo", "hubspot")}
    transports = {p: adapter(p, io) for p, io in http.items()}

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
    brands: list[dict[str, Any]] = []
    for i, (client, crm, platform, external) in enumerate(
        zip(
            clients,
            ("klaviyo", "hubspot"),
            ("google_ads", "meta_ads"),
            ("1234567890", "9876543210"),
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
        policy = MandateDefinition(
            goal_id=goal["id"],
            goal_revision=1,
            currency="USD",
            time_zone="UTC",
            starts_at=NOW - timedelta(hours=1),
            ends_at=NOW + timedelta(days=1),
            accounts=[scope],
            total_cap_micros=50_000_000,
            per_action_cap_micros=40_000_000,
            positive_change_cap_micros=20,
            action_limit=10,
            cooldown_seconds=0,
            freshness_seconds=300,
            allowed_actions=["new_campaign", "creative"],
        )
        mandate = ok(
            client.post(root + "/mandates", headers=headers, json=policy.model_dump(mode="json")),
            201,
        )
        ok(
            client.post(
                root + "/mandates/" + mandate["id"] + "/approve",
                headers=headers,
                json={"expected_revision": 1},
            )
        )
        with Session(customer_engine) as db:
            from app.mandates.models import Mandate

            saved = db.get(Mandate, mandate["id"])
            assert saved
            body = campaign_definition(
                db, saved, scope.model_copy(update={"platform": "google_ads"})
            ).model_dump(mode="json")
            body["account"] = scope.model_dump(mode="json")
        body.update(
            starts_at=(NOW - timedelta(hours=1)).isoformat(),
            ends_at=(NOW + timedelta(hours=23, seconds=-1)).isoformat(),
            budget_micros=40,
        )
        if i:
            uploaded = ok(
                client.post(
                    root + "/media", headers={**headers, "Content-Type": "image/png"}, content=png()
                )
            )
            content = reviewed().source.definition.content.model_dump(mode="json")
            content["media"] = {"media_id": uploaded["media_id"], "sha256": uploaded["sha256"]}
            body.update(
                content=content,
                budget_micros=40_000_000,
                starts_at=NOW.isoformat(),
                ends_at=(NOW + timedelta(hours=1)).isoformat(),
            )
        draft = ok(client.post(root + "/campaign-drafts", headers=headers, json=body))
        review = ok(client.get(root + "/campaign-drafts/" + draft["draft_id"] + "/preview"))
        approved = ok(
            client.post(
                root + "/campaign-drafts/" + draft["draft_id"] + "/approve",
                headers=headers,
                json={"expected_revision": 1, "review_digest": review["review_digest"]},
            )
        )
        assert approved["approved_for_offline_plan"] is True
        brands.append(
            dict(
                actor=actor,
                wid=wid,
                root=root,
                headers=headers,
                scope=scope,
                goal=goal["id"],
                draft=draft["draft_id"],
                connection=connection,
                crm=crm,
                policy=policy,
            )
        )
    a, b = brands
    assert a["wid"] != b["wid"] and a["actor"] != b["actor"]
    assert a["scope"].account_id != b["scope"].account_id
    assert a["scope"].connection_id != b["scope"].connection_id
    for own, foreign, client in ((a, b, clients[0]), (b, a, clients[1])):
        for suffix in (
            "/goals/" + foreign["goal"],
            "/campaign-drafts/" + foreign["draft"] + "/preview",
            "/sources/" + foreign["crm"],
            "/activity",
        ):
            assert client.get(foreign["root"] + suffix).status_code == 404
        assert client.get(own["root"] + "/goals/" + foreign["goal"]).status_code == 404
        assert (
            client.get(
                own["root"] + "/campaign-drafts/" + foreign["draft"] + "/preview"
            ).status_code
            == 404
        )
    # No customer dispatch API exists. This explicit coordinator boundary uses the
    # same API-created owner, confirmed goal and exact approved source draft.
    scope = a["scope"]
    execution_policy = ProviderMandatePolicy(
        environment="contract_test",
        workspace_id=a["wid"],
        goal_id=a["goal"],
        goal_revision=1,
        currency="USD",
        time_zone="UTC",
        starts_at=NOW - timedelta(hours=1),
        ends_at=NOW + timedelta(days=1),
        accounts=[
            ExecutionAccount(
                workspace_id=a["wid"],
                account=scope,
                external_advertiser_id="1234567890",
                connection_version="placeholder",
            )
        ],
        total_cap_micros=100,
        per_plan_cap_micros=80,
        positive_change_cap_micros=20,
        action_limit=10,
        cooldown_seconds=0,
        freshness_seconds=300,
        aggressiveness_percent=5,
        allowed_purposes=["create_paused", "activate"],
        campaign_and_creative_policy="new_exact_review_required",
        activation_policy="separate_exact_approval",
    )
    with Session(customer_engine) as db:
        native = db.scalar(
            select(GoogleCustomerConnection).where(
                GoogleCustomerConnection.workspace_id == a["wid"]
            )
        )
        assert native
        account = execution_policy.accounts[0].model_copy(
            update={"connection_version": f"google:{native.id}:{native.generation}"}
        )
        execution_policy = execution_policy.model_copy(update={"accounts": [account]})
    def pilot_execution_setup(
        *_args: object, total_budget: bool = False
    ) -> tuple[ProviderMandatePolicy, str]:
        assert total_budget is False  # This pilot's reviewed fixture uses a daily budget.
        return execution_policy, a["actor"]

    monkeypatch.setattr(creation_fixture, "setup", pilot_execution_setup)
    server = Server()
    with Session(customer_engine) as db:
        wid, parent, actor, store, runtime, binding = activation_ready(
            db, configuration, tmp_path, server
        )
        row = activation_review.prepare_activation(
            db, wid, parent, binding, actor, store, runtime, lambda: NOW
        )
        activation_review.approve_activation(
            db, wid, row.id, row.digest, row.plan_digest, actor, store, runtime, lambda: NOW
        )
        run = activation_review.create_run(db, wid, row.id, actor, store, runtime, lambda: NOW)
        execute = runtime_for(runtime, server)
        while claim := activation.claim_step(db, wid, run.id, actor, store, execute, lambda: NOW):
            assert (
                activation.execute_claim(db, claim, actor, store, execute, lambda: NOW).outcome
                == "verified_target_state"
            )
        attempt = db.scalar(
            select(ProviderExecutionAttempt).where(ProviderExecutionAttempt.run_id == run.id)
        )
        assert attempt
        attempt_id = attempt.id
        with pytest.raises(HTTPException):
            coordinator.read_owned_outcome_receipt(db, b["wid"], attempt_id, b["actor"])
        db.rollback()
        with pytest.raises(HTTPException):
            coordinator.read_owned_outcome_receipt(db, wid, attempt_id, b["actor"])
        db.rollback()
        assert coordinator.read_owned_outcome_receipt(db, wid, attempt_id, actor)
    before = server.activations
    preview = ok(
        clients[0].post(
            a["root"] + "/closure-preview",
            headers={**a["headers"], "Idempotency-Key": "pilot-close-request-0001"},
            json={},
        )
    )
    closure = ok(
        clients[0].post(
            a["root"] + "/closures/" + preview["request_id"] + "/confirm",
            headers=a["headers"],
            json={
                "expected_revision": preview["revision"],
                "inventory_digest": preview["inventory_digest"],
                "confirm_workspace_id": a["wid"],
            },
        )
    )
    assert closure["closed"] is False and closure["data_erased"] is False
    saved = a["root"] + "/closures/" + preview["request_id"]
    assert clients[0].get(saved).status_code == 200
    assert clients[1].get(saved).status_code in {403, 404}
    assert clients[1].get(b["root"] + "/goals/" + b["goal"]).status_code == 200
    assert clients[1].get(b["root"] + "/sources/hubspot").status_code == 200
    with Session(customer_engine) as db:
        assert coordinator.read_owned_outcome_receipt(db, a["wid"], attempt_id, a["actor"])
        held = list(
            db.scalars(
                select(ProviderExposureReservation).where(
                    ProviderExposureReservation.workspace_id == a["wid"]
                )
            )
        )
        assert held and all(r.state == "held" for r in held)
    assert server.activations == before
