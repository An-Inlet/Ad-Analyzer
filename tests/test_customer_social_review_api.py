from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from app.api.customer_social_review import router
from app.campaign_review.storage import get_media_store
from app.customers.models import CustomerUser
from app.publication.social_review_contracts import (
    LegacySocialConfigurationDocumentV1,
    SocialRequirements,
)
from app.publication.social_review_models import (
    SocialConfigurationApproval,
    SocialConfigurationReview,
)
from app.publication.social_review_runtime import SocialReviewRuntime, get_social_review_runtime
from app.publication.social_review_service import approval_digest
from app.settings import Settings
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_campaign_video import encoded as encoded
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import ISSUER, ORIGIN, FakeProvider, login
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration
from tests.test_social_customer_producer import fixture


@pytest.mark.parametrize("platform", ["meta_ads", "tiktok_ads"])
def test_owned_exact_no_dsa_api(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    encoded: Any,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    platform: str,
) -> None:
    alice, bob, _ = replicas
    with Session(customer_engine) as db:
        original, account, catalog, producer, actor, store, cover, _ = fixture(
            db, configuration, tmp_path, platform, encoded() if platform == "tiktok_ads" else None
        )
        profile = next(iter(producer.profiles.values()))
        if platform == "meta_ads":
            profile = profile.model_copy(update={"dsa_required": False})
        option = catalog.options[0].model_copy(update={"profile_digest": profile.digest()})
        catalog = catalog.model_copy(update={"options": [option]})
        user = db.get(CustomerUser, actor)
        assert user is not None
        user.issuer, user.subject = ISSUER, "social-owner"
        db.commit()
    runtime = SocialReviewRuntime(
        environment="contract_test",
        catalog=lambda request, now: catalog,
        profiles=(profile,),
        requirements={
            profile.digest(): SocialRequirements(
                profile_digest=profile.digest(),
                requirements_digest="a" * 64,
                wording_version="contract-test-v1",
                verified=True,
                dsa_required=False,
                wording="Offline Test: Review This No-DSA Profile And Its Exact Media.",
            )
        },
        clock=lambda: NOW,
    )
    for client in (alice, bob):
        assert isinstance(client.app, FastAPI)
        client.app.include_router(router)
        client.app.dependency_overrides[get_media_store] = lambda: store
        client.app.dependency_overrides[get_social_review_runtime] = lambda: runtime
    login(alice, "social-owner:1")
    login(bob, "other:1")
    headers = {"Origin": ORIGIN, "X-CSRF-Token": alice.cookies.get("__Host-inlet_csrf", "") or ""}
    base = f"/api/customer/v1/workspaces/{account.workspace_id}/execution/social"
    intent = {
        "draft_id": original.review.source.draft_id,
        "draft_revision": original.review.source.revision,
    }
    assert isinstance(alice.app, FastAPI)
    alice.app.dependency_overrides[get_social_review_runtime] = lambda: None
    assert alice.post(base + "/options", json=intent, headers=headers).status_code == 503
    alice.app.dependency_overrides[get_social_review_runtime] = lambda: runtime
    options = alice.post(base + "/options", json=intent, headers=headers)
    assert options.status_code == 200, options.text
    assert options.json()["options"][0]["name"] == option.label
    answer: dict[str, Any] = {"kind": "meta_no_dsa", "special_category_answer": "none_applicable"}
    if platform == "tiktok_ads":
        answer = {"kind": "tiktok_cover", "reviewed_pair": True}
    body = {
        **intent,
        "option_id": options.json()["options"][0]["id"],
        "answer": answer,
        "cover_media_id": cover,
    }
    assert alice.post(base + "/reviews", json=body).status_code == 403
    bad = {**body, "answer": {**answer, "dsa_beneficiary": "Do not accept"}}
    assert alice.post(base + "/reviews", json=bad, headers=headers).status_code == 422
    response = alice.post(base + "/reviews", json=body, headers=headers)
    assert response.status_code == 201, response.text
    review = response.json()
    assert not review["currently_executable"]
    saved = base + "/reviews/" + review["id"]
    assert bob.get(saved).status_code == 403
    confirm_body = {"expected_digest": review["digest"], "acknowledged": True}
    confirmed = alice.post(saved + "/confirmation", json=confirm_body, headers=headers)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed_historical"
    assert (
        alice.post(saved + "/confirmation", json=confirm_body, headers=headers).status_code == 200
    )
    assert (
        alice.post(
            saved + "/confirmation",
            json={**confirm_body, "expected_digest": "f" * 64},
            headers=headers,
        ).status_code
        == 409
    )
    # Seed an actual pre-v2 persisted review/approval; never rewrite or upgrade
    # its original hash on historical API read or attempted confirmation.
    with Session(customer_engine) as db:
        row = db.get(SocialConfigurationReview, review["id"])
        assert row is not None
        legacy = LegacySocialConfigurationDocumentV1.model_validate(
            {
                **{
                    k: v
                    for k, v in row.document.items()
                    if k not in {"configuration", "configuration_digest"}
                },
                "schema_version": "inlet.social-configuration-review.v1",
                "requirements": {
                    k: v for k, v in row.document["requirements"].items() if k != "wording"
                },
            }
        )
        legacy_id = uuid4().hex
        values = {column.name: getattr(row, column.name) for column in row.__table__.columns}
        db.add(
            SocialConfigurationReview(
                **{
                    **values,
                    "id": legacy_id,
                    "document": legacy.model_dump(mode="json"),
                    "digest": legacy.digest(),
                }
            )
        )
        db.flush()
        historical_approval = SocialConfigurationApproval(
            review_id=legacy_id,
            workspace_id=account.workspace_id,
            review_digest=legacy.digest(),
            actor=actor,
            confirmed_at=NOW,
        )
        historical_approval.digest = approval_digest(historical_approval)
        db.add(historical_approval)
        db.commit()
    historical_path = base + "/reviews/" + legacy_id
    history = alice.get(historical_path)
    assert history.status_code == 200, history.text
    assert history.json()["status"] == "requires_new_review"
    assert history.json()["digest"] == legacy.digest()
    assert history.json()["configuration"] is None
    assert (
        alice.post(
            historical_path + "/confirmation",
            headers=headers,
            json={"expected_digest": legacy.digest(), "acknowledged": True},
        ).status_code
        == 409
    )
    with Session(customer_engine) as db:
        preserved = db.get(SocialConfigurationReview, legacy_id)
        assert preserved is not None and preserved.digest == legacy.digest()
    assert alice.delete("/api/customer/v1/session", headers=headers).status_code == 204
    assert alice.get(saved).status_code == 401
