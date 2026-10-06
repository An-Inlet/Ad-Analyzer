"""Real customer routes, persisted coordinator evidence and mocked provider HTTP."""

import json
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.ads.models import AdvertisingAccount
from app.api.customer_execution import router
from app.campaign_review.storage import get_media_store
from app.collectors.google_catalog import GoogleCatalogContext, GoogleCatalogHTTP
from app.customers.models import CustomerUser
from app.publication import execution_mandates as mandates
from app.publication.activation_review import ActivationReviewRuntime
from app.publication.customer_runtime import (
    CustomerExecutionRuntime,
    get_customer_execution_runtime,
)
from app.publication.execution_contracts import ExposureEvidence
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionMandate,
    ProviderExecutionReview,
    ProviderExecutionRun,
    ProviderExposureReservation,
)
from app.publication.provider_contracts import ProviderContext
from app.settings import Settings
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_activation_coordinator import runtime_for
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import ISSUER, ORIGIN, FakeProvider, login
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_google_activation import Server
from tests.test_provider_coordinator import GoogleServer, ready
from tests.test_provider_qualification import adapter, response_rows
from tests.test_shopify_sales import configuration as configuration


def setup_api(
    db: Session, config: Settings, path: Path
) -> tuple[int, str, dict[str, Any], dict[str, Any], Any, CustomerExecutionRuntime, GoogleServer]:
    server = Server()
    wid, run_id, actor, media, creation = ready(db, config, path, server)
    run = db.get(ProviderExecutionRun, run_id)
    assert run is not None
    review = db.get(ProviderExecutionReview, run.review_id)
    assert review is not None
    document = review.document
    mandate = db.scalar(
        select(ProviderExecutionMandate).where(ProviderExecutionMandate.workspace_id == wid)
    )
    assert mandate is not None
    policy = mandates.policy(db, mandate)
    p = policy.model_dump(
        mode="json",
        exclude={
            "schema_version",
            "environment",
            "workspace_id",
            "accounts",
            "freshness_seconds",
            "allowed_target_set_digest",
            "campaign_and_creative_policy",
            "activation_policy",
        },
    )
    p["account_ids"] = [a.account.account_id for a in policy.accounts]
    user = db.get(CustomerUser, actor)
    account = db.get(AdvertisingAccount, policy.accounts[0].account.account_id)
    assert user is not None and account is not None
    user.issuer, user.subject = ISSUER, "execution-owner"
    account.time_zone = "Pacific/Pago_Pago"
    db.commit()
    rows = response_rows()
    rows["customer"]["timeZone"] = "Pacific/Pago_Pago"

    rows["customer"]["resourceName"] = "customers/1234567890"
    rows["customConversionGoal"]["name"] = "Shop Purchases"
    rows["conversionAction"]["ownerCustomer"] = "customers/1234567890"

    def catalog_http(request: httpx.Request) -> httpx.Response:
        query = json.loads(request.content)["query"]
        table = query.split(" FROM ")[1].split()[0]
        key = table.split("_")[0] + "".join(p.title() for p in table.split("_")[1:])
        return httpx.Response(200, json={"results": [{key: rows[key]}]})

    catalog = GoogleCatalogHTTP(
        lambda req, now: GoogleCatalogContext(
            account=req.account,
            request_digest=req.digest(),
            expires_at=now + timedelta(minutes=2),
            access_token=SecretStr("mock-only"),
        ),
        transport=httpx.MockTransport(catalog_http),
        clock=lambda: NOW,
    )

    def activation_exposure(
        session: Session, binding: Any, plan: Any, reservation_id: str, now: Any
    ) -> ExposureEvidence:
        base = creation.exposure_reader(session, binding, plan, now)
        reservation = session.get(ProviderExposureReservation, reservation_id)
        assert reservation is not None and base.portfolio_upper_micros is not None
        return ExposureEvidence.model_validate(
            base.model_copy(
                update={
                    "existing_reservations_micros": base.existing_reservations_micros
                    - reservation.amount_micros,
                    "portfolio_upper_micros": base.portfolio_upper_micros
                    - reservation.amount_micros,
                }
            ).model_dump(mode="json")
        )

    runtime = CustomerExecutionRuntime(
        creation=creation,
        activation=runtime_for(ActivationReviewRuntime(creation, activation_exposure), server),
        google_qualification=adapter(rows),
        google_context=lambda scope: ProviderContext(
            scope=scope,
            login_customer_id=None,
            access_token=SecretStr("mock-only"),
            expires_at=NOW + timedelta(hours=1),
        ),
        catalog=catalog,
        clock=lambda: NOW,
    )
    return wid, actor, p, document, media, runtime, server


def install(client: TestClient, runtime: CustomerExecutionRuntime | None, media: Any) -> None:
    client.app.include_router(router)  # type: ignore[attr-defined]
    client.app.dependency_overrides[get_customer_execution_runtime] = lambda: runtime  # type: ignore[attr-defined]
    client.app.dependency_overrides[get_media_store] = lambda: media  # type: ignore[attr-defined]


def test_default_runtime_and_forged_authority_are_denied(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    replicas: tuple[TestClient, TestClient, FakeProvider],
) -> None:
    alice, _, _ = replicas
    with Session(customer_engine) as db:
        wid, _, p, _, media, _, server = setup_api(db, configuration, tmp_path)
    install(alice, None, media)
    login(alice, "execution-owner:1")
    base = f"/api/customer/v1/workspaces/{wid}/execution"
    headers = {"Origin": ORIGIN, "X-CSRF-Token": alice.cookies.get("__Host-inlet_csrf") or ""}
    status = alice.get(base + "/capabilities")
    assert status.status_code == 200 and not any(v["available"] for v in status.json()["providers"])
    assert alice.post(base + "/mandates", json=p, headers=headers).status_code == 409
    assert (
        alice.post(
            base + "/mandates", json={**p, "environment": "live"}, headers=headers
        ).status_code
        == 422
    )
    assert server.posts == 0


def test_actual_customer_consent_review_creation_and_receipts(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    replicas: tuple[TestClient, TestClient, FakeProvider],
) -> None:
    alice, bob, _ = replicas
    with Session(customer_engine) as db:
        wid, _, p, document, media, runtime, server = setup_api(db, configuration, tmp_path)
    install(alice, runtime, media)
    install(bob, runtime, media)
    login(alice, "execution-owner:1")
    login(bob, "other-owner:1")
    base = f"/api/customer/v1/workspaces/{wid}/execution"
    headers = {"Origin": ORIGIN, "X-CSRF-Token": alice.cookies.get("__Host-inlet_csrf") or ""}

    def post(path: str, body: Any = None, expected: int = 200) -> Any:
        response = alice.post(base + path, json=body, headers=headers)
        assert response.status_code == expected, response.text
        return response.json()

    assert alice.post(base + "/mandates", json=p, headers={"Origin": ORIGIN}).status_code == 403
    assert bob.get(base + "/mandates").status_code == 403
    policy = post("/mandates", p, 201)
    assert server.posts == 0
    draft = document["plan"]["review"]["source"]
    catalog = post("/configuration-options", {"draft_id": draft["draft_id"]})
    assert catalog["options"][0]["name"] == "Shop Purchases"
    assert "customConversionGoals" not in str(catalog)
    intent = {
        "draft_id": draft["draft_id"],
        "draft_revision": draft["revision"],
        "mandate_id": policy["id"],
        "mandate_revision": policy["revision"],
        "google": {
            "catalog_option_id": catalog["options"][0]["id"],
            "daily_budget_micros": 20,
            "max_cpc_micros": 1,
            "search_partners": False,
        },
    }
    assert alice.post(base + "/creation-reviews", json=intent, headers=headers).status_code == 409
    post(
        f"/mandates/{policy['id']}/consent",
        {"expected_revision": policy["revision"], "policy_digest": policy["policy_digest"]},
    )
    reviewed = post("/creation-reviews", intent, 201)
    assert reviewed["purpose"] == "create_paused" and reviewed["environment"] == "contract_test"
    assert alice.post(base + f"/reviews/{reviewed['id']}/runs", headers=headers).status_code == 409
    assert (
        alice.post(
            base + f"/reviews/{reviewed['id']}/approval",
            json={"review_digest": "0" * 64, "plan_digest": reviewed["plan_digest"]},
            headers=headers,
        ).status_code
        == 409
    )
    post(
        f"/reviews/{reviewed['id']}/approval",
        {"review_digest": reviewed["review_digest"], "plan_digest": reviewed["plan_digest"]},
    )
    run = post(f"/reviews/{reviewed['id']}/runs", expected=201)
    assert post(f"/reviews/{reviewed['id']}/runs", expected=201)["id"] == run["id"]
    for _ in range(30):
        run = post(f"/runs/{run['id']}/advance")
        if run["state"] == "created_paused":
            break
    assert run["state"] == "created_paused" and server.posts > 0
    count = server.posts
    post(f"/runs/{run['id']}/advance")
    assert server.posts == count
    with Session(customer_engine) as db:
        attempt = db.scalar(
            select(ProviderExecutionAttempt).where(ProviderExecutionAttempt.run_id == run["id"])
        )
        assert attempt is not None
        identifier = attempt.id
    receipt = alice.get(base + f"/attempts/{identifier}/receipt")
    assert receipt.status_code == 200 and receipt.json()["receipt"]["outcome"] == "verified_effect"
    assert "mock-only" not in receipt.text
    activation = post(
        "/activation-reviews",
        {
            "parent_run_id": run["id"],
            "mandate_id": policy["id"],
            "mandate_revision": policy["revision"],
        },
        201,
    )
    assert activation["purpose"] == "activate"
    assert (
        alice.post(base + f"/reviews/{activation['id']}/runs", headers=headers).status_code == 409
    )
    post(
        f"/reviews/{activation['id']}/approval",
        {"review_digest": activation["review_digest"], "plan_digest": activation["plan_digest"]},
    )
    activated = post(f"/reviews/{activation['id']}/runs", expected=201)
    for _ in range(30):
        activated = post(f"/runs/{activated['id']}/advance")
        if activated["state"] == "activation_observed":
            break
    assert activated["state"] == "activation_observed"
    assert (
        activated["effective_time"] == "unavailable" and activated["reservation_retained"] is True
    )
    assert alice.delete("/api/customer/v1/session", headers=headers).status_code == 204
    assert alice.get(base + f"/runs/{run['id']}").status_code == 401


@pytest.mark.parametrize("stage", ["catalog", "qualification"])
def test_original_session_revoked_during_read_io_cannot_persist_review(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
) -> None:
    from app.customers.access import digest
    from app.customers.models import CustomerSession
    from sqlalchemy import func

    alice, _, _ = replicas
    with Session(customer_engine) as db:
        wid, _, _, document, media, runtime, server = setup_api(db, configuration, tmp_path)
        before = db.scalar(select(func.count()).select_from(ProviderExecutionReview))
    install(alice, runtime, media)
    login(alice, "execution-owner:revocation")
    session_digest = digest(alice.cookies.get("__Host-inlet_session") or "")
    base = f"/api/customer/v1/workspaces/{wid}/execution"
    headers = {"Origin": ORIGIN, "X-CSRF-Token": alice.cookies.get("__Host-inlet_csrf") or ""}
    draft = document["plan"]["review"]["source"]
    catalog_response = alice.post(
        base + "/configuration-options", json={"draft_id": draft["draft_id"]}, headers=headers
    )
    assert catalog_response.status_code == 200, catalog_response.text

    def revoke() -> None:
        with Session(customer_engine) as other:
            session = other.get(CustomerSession, session_digest)
            assert session is not None
            session.revoked_at = 1
            other.commit()

    if stage == "catalog":
        old_reader = runtime.catalog
        assert old_reader is not None

        def revoke_catalog(*args: Any) -> Any:
            result = old_reader(*args)
            revoke()
            return result

        install(alice, replace(runtime, catalog=revoke_catalog), media)
    else:
        old_post = runtime.google_qualification._post

        def revoke_after_read(*args: Any, **kwargs: Any) -> Any:
            result = old_post(*args, **kwargs)
            revoke()
            return result

        monkeypatch.setattr(runtime.google_qualification, "_post", revoke_after_read)
    body = {
        "draft_id": draft["draft_id"],
        "draft_revision": draft["revision"],
        "mandate_id": document["mandate"]["mandate_id"],
        "mandate_revision": document["mandate"]["revision"],
        "google": {
            "catalog_option_id": catalog_response.json()["options"][0]["id"],
            "daily_budget_micros": 20,
            "max_cpc_micros": 1,
            "search_partners": False,
        },
    }
    denied = alice.post(base + "/creation-reviews", json=body, headers=headers)
    assert denied.status_code == 401, denied.text
    assert server.posts == 0
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderExecutionReview)) == before


def test_unknown_execution_is_not_replayed_and_forged_proofs_rejected(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    replicas: tuple[TestClient, TestClient, FakeProvider],
) -> None:
    alice, _, _ = replicas
    with Session(customer_engine) as db:
        wid, _, _, document, media, runtime, server = setup_api(db, configuration, tmp_path)
        run = db.scalar(
            select(ProviderExecutionRun).where(ProviderExecutionRun.workspace_id == wid)
        )
        assert run is not None
        identifier = run.id
    install(alice, runtime, media)
    login(alice, "execution-owner:unknown")
    headers = {"Origin": ORIGIN, "X-CSRF-Token": alice.cookies.get("__Host-inlet_csrf") or ""}
    base = f"/api/customer/v1/workspaces/{wid}/execution"
    draft = document["plan"]["review"]["source"]
    forged = {"draft_id": draft["draft_id"], "qualification": {"eligible": True}}
    assert (
        alice.post(base + "/configuration-options", json=forged, headers=headers).status_code == 422
    )
    server.timeout, server.absent = True, True
    first = alice.post(base + f"/runs/{identifier}/advance", headers=headers)
    assert first.status_code == 200 and first.json()["state"] == "unknown", first.text
    assert first.json()["reservation_retained"]
    posts = server.posts
    assert alice.post(base + f"/runs/{identifier}/advance", headers=headers).status_code == 200
    assert server.posts == posts == 1
    assert (
        alice.post(
            base + f"/runs/{identifier}/reconcile",
            json={"attempt_id": "f" * 32, "outcome": "verified_no_effect"},
            headers=headers,
        ).status_code
        == 422
    )


def test_logout_during_admitted_dispatch_preserves_receipt_but_denies_response(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.customers.access import digest
    from app.customers.models import CustomerSession
    from app.publication.execution_models import ProviderExecutionReceipt

    alice, _, _ = replicas
    with Session(customer_engine) as db:
        wid, _, _, _, media, runtime, server = setup_api(db, configuration, tmp_path)
        run = db.scalar(
            select(ProviderExecutionRun).where(ProviderExecutionRun.workspace_id == wid)
        )
        assert run is not None
        identifier = run.id
    install(alice, runtime, media)
    login(alice, "execution-owner:admitted")
    session_digest = digest(alice.cookies.get("__Host-inlet_session") or "")
    headers = {"Origin": ORIGIN, "X-CSRF-Token": alice.cookies.get("__Host-inlet_csrf") or ""}
    old_apply = runtime.creation.google.apply_once

    def revoke_during_apply(*args: Any, **kwargs: Any) -> Any:
        with Session(customer_engine) as other:
            session = other.get(CustomerSession, session_digest)
            assert session is not None
            session.revoked_at = 1
            other.commit()
        return old_apply(*args, **kwargs)

    monkeypatch.setattr(runtime.creation.google, "apply_once", revoke_during_apply)
    base = f"/api/customer/v1/workspaces/{wid}/execution"
    response = alice.post(base + f"/runs/{identifier}/advance", headers=headers)
    assert response.status_code == 401, response.text
    assert server.posts == 1  # Already admitted in-flight request cannot be recalled.
    with Session(customer_engine) as db:
        assert (
            db.scalar(
                select(ProviderExecutionReceipt.id).where(
                    ProviderExecutionReceipt.workspace_id == wid
                )
            )
            is not None
        )
    assert alice.post(base + f"/runs/{identifier}/advance", headers=headers).status_code == 401
    assert server.posts == 1
