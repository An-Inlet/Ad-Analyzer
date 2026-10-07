"""Customer social intents exercise real durable coordinators with mock-only HTTP."""

from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from app.api.customer_social_execution import router as execution_router
from app.api.customer_social_review import router as configuration_router
from app.customers.models import CustomerUser
from app.executors.google_publication import GooglePublicationHTTP
from app.executors.meta_activation import MetaActivationHTTP
from app.executors.meta_publication import MetaPublicationTransport
from app.executors.tiktok_activation import TikTokActivationHTTP
from app.executors.tiktok_publication import TikTokPublicationTransport
from app.publication.activation_review import ActivationReviewRuntime
from app.publication.coordinator_contracts import ConfigurationQualification, CreationRuntime
from app.publication.customer_runtime import (
    CustomerExecutionRuntime,
    get_customer_execution_runtime,
)
from app.publication.execution_contracts import ExposureEvidence
from app.publication.execution_models import ProviderExecutionMandate, ProviderExposureReservation
from app.publication.scoped_media import ScopedProviderMediaReader
from app.publication.social_catalog import MetaConfigurationProfile
from app.publication.social_contracts import ProviderMediaBinding
from app.publication.social_review_contracts import SocialRequirements
from app.publication.social_review_runtime import SocialReviewRuntime, get_social_review_runtime
from app.settings import Settings
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests import test_social_customer_producer as producer_fixture
from tests.test_campaign_video import encoded as encoded
from tests.test_commerce_measurement import NOW
from tests.test_customer_execution_api import install
from tests.test_customer_identity import ISSUER, ORIGIN, FakeProvider, login
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration
from tests.test_social_activation_journeys import Server, runtime_for
from tests.test_social_coordinator_journeys import ready_legacy as social_ready


def setup_social(
    db: Session,
    configuration: Settings,
    tmp_path: Path,
    platform: str,
    video: bytes | None,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Any, ...]:
    db.expire_on_commit = False
    captured: list[CreationRuntime] = []
    native_server = Server(platform)
    ready = cast(Callable[..., Any], social_ready)

    def observe(*args: Any) -> Any:
        result = ready(*args[:-1], native_server)
        captured.append(result[4])
        return result

    with monkeypatch.context() as patch:
        patch.setattr(producer_fixture, "ready", observe)
        original, account, catalog, producer, actor, store, cover, _ = producer_fixture.fixture(
            db,
            configuration,
            tmp_path,
            platform,
            video,
        )
    profile = next(iter(producer.profiles.values()))
    if isinstance(profile, MetaConfigurationProfile):
        profile = profile.model_copy(update={"dsa_required": False})
    option = catalog.options[0].model_copy(update={"profile_digest": profile.digest()})
    catalog = catalog.model_copy(update={"options": [option]})
    user = db.get(CustomerUser, actor)
    assert user is not None
    user.issuer, user.subject = ISSUER, "social-execution-owner"
    db.commit()
    discovery = SocialReviewRuntime(
        "contract_test",
        lambda request, now: catalog,
        (profile,),
        {
            profile.digest(): SocialRequirements(
                profile_digest=profile.digest(),
                requirements_digest="a" * 64,
                wording_version="offline-v1",
                verified=True,
                dsa_required=False,
                wording="Offline Profile: Explicit No Special Category And Exact Media.",
            )
        },
        lambda: NOW,
    )

    def qualification(plan: Any, now: Any) -> ConfigurationQualification:
        return ConfigurationQualification(
            environment="contract_test",
            account=account,
            plan_digest=plan.digest(),
            api_version=plan.api_version,
            observed_at=now,
            expires_at=now + timedelta(minutes=5),
            evidence_digest=plan.digest(),
            checks_version="offline_exact_social",
            unresolved=[],
        )

    engine = db.get_bind()

    class Reader:
        def read_verified(self, wid: int, binding: ProviderMediaBinding) -> bytes:
            with Session(engine) as fresh:
                return ScopedProviderMediaReader(fresh, store).read_verified(wid, binding)

    media_reader = Reader()
    creation = replace(
        captured[0],
        qualification_reader=qualification,
        meta=MetaPublicationTransport(media_reader, transport=httpx.MockTransport(native_server)),
        tiktok=TikTokPublicationTransport(
            media_reader, transport=httpx.MockTransport(native_server)
        ),
    )

    def exposure(
        session: Session, binding: Any, plan: Any, reservation_id: str, now: Any
    ) -> ExposureEvidence:
        base = creation.exposure_reader(session, binding, plan, now)
        held = session.get(ProviderExposureReservation, reservation_id)
        assert held is not None and base.portfolio_upper_micros is not None
        return ExposureEvidence.model_validate(
            base.model_copy(
                update={
                    "existing_reservations_micros": base.existing_reservations_micros
                    - held.amount_micros,
                    "portfolio_upper_micros": base.portfolio_upper_micros - held.amount_micros,
                }
            ).model_dump()
        )

    runtime = CustomerExecutionRuntime(
        creation,
        replace(
            runtime_for(db, store, ActivationReviewRuntime(creation, exposure), native_server),
            meta=MetaActivationHTTP(media_reader, transport=httpx.MockTransport(native_server)),
            tiktok=TikTokActivationHTTP(media_reader, transport=httpx.MockTransport(native_server)),
        ),
        GooglePublicationHTTP(
            transport=httpx.MockTransport(
                lambda _: (_ for _ in ()).throw(AssertionError("unexpected Google"))
            )
        ),
        lambda _: (_ for _ in ()).throw(AssertionError("unexpected Google context")),
        clock=lambda: NOW,
        social_review=discovery,
    )
    mandate = db.scalar(
        select(ProviderExecutionMandate).where(
            ProviderExecutionMandate.workspace_id == account.workspace_id
        )
    )
    assert mandate is not None
    return original, account, actor, store, cover, runtime, mandate.id, native_server


def configure(client: TestClient, runtime: CustomerExecutionRuntime, store: Any) -> None:
    install(client, runtime, store)
    assert isinstance(client.app, FastAPI)
    client.app.include_router(configuration_router)
    client.app.include_router(execution_router)
    client.app.dependency_overrides[get_social_review_runtime] = lambda: runtime.social_review


def confirmed(
    client: TestClient, base: str, original: Any, cover: str | None, headers: dict[str, str]
) -> dict[str, Any]:
    body = {
        "draft_id": original.review.source.draft_id,
        "draft_revision": original.review.source.revision,
    }
    response = client.post(base + "/social/options", json=body, headers=headers)
    assert response.status_code == 200, response.text
    answer: dict[str, Any] = (
        {"kind": "meta_no_dsa", "special_category_answer": "none_applicable"}
        if cover is None
        else {"kind": "tiktok_cover", "reviewed_pair": True}
    )
    response = client.post(
        base + "/social/reviews",
        json={
            **body,
            "option_id": response.json()["options"][0]["id"],
            "answer": answer,
            "cover_media_id": cover,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    row = response.json()
    assert isinstance(row, dict)
    response = client.post(
        base + "/social/reviews/" + row["id"] + "/confirmation",
        json={"expected_digest": row["digest"], "acknowledged": True},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return row


@pytest.mark.parametrize("platform", ["meta_ads", "tiktok_ads"])
def test_social_customer_paused_creation_and_activation(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    encoded: Any,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
) -> None:
    alice, bob, _ = replicas
    with Session(customer_engine) as db:
        original, account, actor, store, cover, runtime, mandate_id, server = setup_social(
            db,
            configuration,
            tmp_path,
            platform,
            encoded() if platform == "tiktok_ads" else None,
            monkeypatch,
        )
    for client in (alice, bob):
        configure(client, runtime, store)
    login(alice, "social-execution-owner:1")
    login(bob, "stranger:1")
    headers = {"Origin": ORIGIN, "X-CSRF-Token": alice.cookies.get("__Host-inlet_csrf", "") or ""}
    base = f"/api/customer/v1/workspaces/{account.workspace_id}/execution"
    config = confirmed(alice, base, original, cover, headers)
    body = {
        "configuration_review_id": config["id"],
        "expected_configuration_digest": config["digest"],
        "mandate_id": mandate_id,
        "mandate_revision": 1,
    }
    assert isinstance(alice.app, FastAPI)
    alice.app.dependency_overrides[get_customer_execution_runtime] = lambda: None
    assert (
        alice.post(base + "/social/creation-reviews", json=body, headers=headers).status_code == 409
    )
    alice.app.dependency_overrides[get_customer_execution_runtime] = lambda: runtime
    assert alice.post(base + "/social/creation-reviews", json=body).status_code == 403
    assert (
        alice.post(
            base + "/social/creation-reviews", json={**body, "plan": {}}, headers=headers
        ).status_code
        == 422
    )
    assert (
        bob.get(
            base + "/social/confirmed-configurations",
            params={"draft_id": original.review.source.draft_id},
        ).status_code
        == 403
    )
    assert (
        alice.post(
            base + "/social/creation-reviews",
            json={**body, "expected_configuration_digest": "f" * 64},
            headers=headers,
        ).status_code
        == 409
    )
    response = alice.post(base + "/social/creation-reviews", json=body, headers=headers)
    if platform == "tiktok_ads":
        # Historical custom configuration remains readable; no new forward review.
        # Future TikTok success/unknown/activation uses the configured linked suite.
        assert response.status_code == 409, response.text
        assert response.json()["detail"] == "tiktok_new_custom_identity_creation_unavailable"
        assert server.posts == server.activations == 0
        return
    assert response.status_code == 201, response.text
    review = response.json()
    assert review["platform"] == platform and review["environment"] == "contract_test"
    assert runtime.social_review is not None
    alice.app.dependency_overrides[get_customer_execution_runtime] = lambda: replace(
        runtime, social_review=replace(runtime.social_review, requirements={})
    )
    changed = alice.post(
        base + "/reviews/" + review["id"] + "/approval",
        json={
            "review_digest": review["review_digest"],
            "plan_digest": review["plan_digest"],
        },
        headers=headers,
    )
    assert changed.status_code == 409, changed.text
    assert server.posts == 0
    alice.app.dependency_overrides[get_customer_execution_runtime] = lambda: runtime
    response = alice.post(
        base + "/reviews/" + review["id"] + "/approval",
        json={"review_digest": review["review_digest"], "plan_digest": review["plan_digest"]},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    response = alice.post(base + "/reviews/" + review["id"] + "/runs", headers=headers)
    assert response.status_code == 201, response.text
    run = response.json()
    for _ in range(6):
        response = alice.post(base + "/runs/" + run["id"] + "/advance", headers=headers)
        assert response.status_code == 200, response.text
        run = response.json()
    assert run["state"] == "created_paused"
    assert server.activations == 0
    # Recovery uses the original owned attempt even if current discovery is absent.
    posts = server.posts
    alice.app.dependency_overrides[get_customer_execution_runtime] = lambda: replace(
        runtime, social_review=None
    )
    recovered = alice.post(
        base + "/runs/" + run["id"] + "/reconcile",
        json={"attempt_id": run["steps"][0]["attempt_id"]},
        headers=headers,
    )
    assert recovered.status_code == 200, recovered.text
    assert server.posts == posts
    alice.app.dependency_overrides[get_customer_execution_runtime] = lambda: runtime
    response = alice.post(
        base + "/activation-reviews",
        json={"parent_run_id": run["id"], "mandate_id": mandate_id, "mandate_revision": 1},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    activation = response.json()
    response = alice.post(
        base + "/reviews/" + activation["id"] + "/approval",
        json={
            "review_digest": activation["review_digest"],
            "plan_digest": activation["plan_digest"],
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    response = alice.post(base + "/reviews/" + activation["id"] + "/runs", headers=headers)
    assert response.status_code == 201, response.text
    activation_run = response.json()
    for _ in range(4):
        response = alice.post(base + "/runs/" + activation_run["id"] + "/advance", headers=headers)
        assert response.status_code == 200, response.text
        activation_run = response.json()
    assert activation_run["state"] == "activation_observed" and server.activations == 3
    assert alice.get(base + "/runs/" + run["id"]).status_code == 200
    assert alice.delete("/api/customer/v1/session", headers=headers).status_code == 204
    assert alice.get(base + "/runs/" + run["id"]).status_code == 401


@pytest.mark.parametrize(
    "change",
    ["session_during_catalog", "expiry_during_qualification", "server_configuration_guard"],
)
def test_social_creation_rechecks_authority_after_io(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    from app.customers.models import CustomerSession
    from app.publication.customer_runtime import get_customer_execution_runtime
    from app.publication.execution_models import ProviderExecutionReview
    from sqlalchemy import func

    alice, _, _ = replicas
    with Session(customer_engine) as db:
        original, account, actor, store, cover, runtime, mandate_id, native = setup_social(
            db,
            configuration,
            tmp_path,
            "meta_ads",
            None,
            monkeypatch,
        )
    configure(alice, runtime, store)
    login(alice, "social-execution-owner:1")
    headers = {"Origin": ORIGIN, "X-CSRF-Token": alice.cookies.get("__Host-inlet_csrf", "") or ""}
    base = f"/api/customer/v1/workspaces/{account.workspace_id}/execution"
    config = confirmed(alice, base, original, cover, headers)
    discovery = runtime.social_review
    assert discovery is not None
    if change == "session_during_catalog":

        def catalog(request: Any, now: Any) -> Any:
            with Session(customer_engine) as separate:
                for row in separate.scalars(
                    select(CustomerSession).where(CustomerSession.user_id == actor)
                ):
                    row.revoked_at = int(NOW.timestamp())
                separate.commit()
            return discovery.catalog(request, now)

        runtime = replace(runtime, social_review=replace(discovery, catalog=catalog))
        expected = 401
    elif change == "server_configuration_guard":
        from fastapi import HTTPException

        def deny(document: Any, now: Any) -> None:
            raise HTTPException(409, "server configuration policy changed")

        runtime = replace(
            runtime, creation=replace(runtime.creation, social_configuration_current=deny)
        )
        expected = 409
    else:
        clock = [NOW]
        qualify = runtime.creation.qualification_reader

        def qualification(plan: Any, now: Any) -> Any:
            result = qualify(plan, now)
            clock[0] = NOW + timedelta(minutes=2)
            return result

        runtime = replace(
            runtime,
            clock=lambda: clock[0],
            creation=replace(runtime.creation, qualification_reader=qualification),
        )
        expected = 409
    assert isinstance(alice.app, FastAPI)
    alice.app.dependency_overrides[get_customer_execution_runtime] = lambda: runtime
    with Session(customer_engine) as db:
        before = db.scalar(select(func.count()).select_from(ProviderExecutionReview))
    response = alice.post(
        base + "/social/creation-reviews",
        json={
            "configuration_review_id": config["id"],
            "expected_configuration_digest": config["digest"],
            "mandate_id": mandate_id,
            "mandate_revision": 1,
        },
        headers=headers,
    )
    assert response.status_code == expected, response.text
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderExecutionReview)) == before
    assert native.posts == 0
