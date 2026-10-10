"""Current read/configuration positives, distinct from historical execution races."""

from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest
from app.api import customer_execution, customer_social_execution, customer_social_review
from app.campaign_review.storage import get_media_store
from app.customers.models import CustomerUser
from app.publication.coordinator_contracts import CreationExecutionReview
from app.publication.customer_runtime import get_customer_execution_runtime
from app.publication.execution_models import ProviderExecutionReview, ProviderExecutionRun
from app.publication.social_review_contracts import SocialRequirements
from app.publication.social_review_runtime import SocialReviewRuntime, get_social_review_runtime
from fastapi import FastAPI
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.social_producer_retained_fixture import graph, load_source, retained_social_producer
from tests.test_campaign_video import encoded as encoded
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import ORIGIN, replicas
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.planning_boundary
@pytest.mark.parametrize("platform", ["meta_ads", "tiktok_ads"])
def test_current_social_configuration_history_and_execution_boundary(
    customer_engine: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configuration: Any,
    encoded: Any,
    platform: str,
) -> None:
    video = encoded() if platform == "tiktok_ads" else None
    with retained_social_producer(
        customer_engine,
        tmp_path / "execution-read-original",
        platform,
        video,
        None,
        consumer="execution_api",
    ) as source:
        alice, bob, identity = cast(Any, replicas).__wrapped__(source.engine, monkeypatch)
        try:
            with Session(source.engine) as db:
                original, account, catalog, producer, actor, store, cover, _ = load_source(
                    db, source
                )
                user = db.get(CustomerUser, actor)
                assert user and user.issuer == "mock" and user.subject == actor
                identity.issuer, identity.email = user.issuer, user.email
                review_row = db.get(ProviderExecutionReview, source.ids.review_id)
                run_row = db.get(ProviderExecutionRun, source.ids.run_id)
                assert review_row and run_row
                review_digest, run_state = review_row.digest, run_row.state
                binding = CreationExecutionReview.model_validate(review_row.document).mandate
                profile = next(iter(producer.profiles.values()))
                if platform == "meta_ads":
                    profile = profile.model_copy(update={"dsa_required": False})
                option = catalog.options[0].model_copy(update={"profile_digest": profile.digest()})
                catalog = catalog.model_copy(update={"options": [option]})
            runtime = SocialReviewRuntime(
                environment="contract_test",
                catalog=lambda request, now: catalog,
                profiles=(profile,),
                requirements={
                    profile.digest(): SocialRequirements(
                        profile_digest=profile.digest(),
                        requirements_digest="a" * 64,
                        wording_version="offline-v1",
                        verified=True,
                        dsa_required=False,
                        wording="Offline Profile: Explicit No Special Category And Exact Media.",
                    )
                },
                clock=lambda: NOW,
            )
            calls: list[str] = []

            def forbidden() -> Any:
                calls.append("forbidden dependency")
                raise AssertionError("Execution dependency must not resolve")

            for client in (alice, bob):
                assert isinstance(client.app, FastAPI)
                for router in (
                    customer_execution.router,
                    customer_social_execution.router,
                    customer_social_review.router,
                ):
                    client.app.include_router(router)
                client.app.dependency_overrides[get_media_store] = lambda: store
                client.app.dependency_overrides[get_social_review_runtime] = lambda: runtime
                client.app.dependency_overrides[get_customer_execution_runtime] = lambda: None
                client.app.dependency_overrides[customer_execution.get_execution_media_factory] = (
                    forbidden
                )
            evidence = source.execution_api_evidence
            assert evidence is not None
            evidence.login(source, alice, bob)
            headers = {"Origin": ORIGIN, "X-CSRF-Token": alice.cookies["__Host-inlet_csrf"]}
            foreign_headers = {"Origin": ORIGIN, "X-CSRF-Token": bob.cookies["__Host-inlet_csrf"]}
            base = f"/api/customer/v1/workspaces/{source.ids.workspace_id}/execution"
            intent = {
                "draft_id": original.review.source.draft_id,
                "draft_revision": original.review.source.revision,
            }
            options = alice.post(base + "/social/options", json=intent, headers=headers)
            assert options.status_code == 200, options.text
            answer = (
                {"kind": "meta_no_dsa", "special_category_answer": "none_applicable"}
                if platform == "meta_ads"
                else {"kind": "tiktok_cover", "reviewed_pair": True}
            )
            body = {
                **intent,
                "option_id": options.json()["options"][0]["id"],
                "answer": answer,
                "cover_media_id": cover,
            }
            before = graph(source.engine)
            assert alice.post(base + "/social/reviews", json=body).status_code == 403
            assert graph(source.engine) == before
            result = alice.post(base + "/social/reviews", json=body, headers=headers)
            assert result.status_code == 201, result.text
            review = result.json()
            assert review["digest"] == evidence.document.digest()
            saved = base + "/social/reviews/" + review["id"]
            result = alice.post(
                saved + "/confirmation",
                headers=headers,
                json={
                    "expected_digest": review["digest"],
                    "acknowledged": True,
                },
            )
            assert result.status_code == 200, result.text
            assert result.json()["status"] == "confirmed_historical"
            paths = (
                saved,
                base
                + "/social/confirmed-configurations?draft_id="
                + original.review.source.draft_id,
                base + "/reviews/" + source.ids.review_id,
                base + "/runs/" + source.ids.run_id,
            )
            for path in paths:
                response = alice.get(path)
                assert response.status_code == 200, response.text
                assert "no-store" in response.headers["cache-control"]
                assert bob.get(path).status_code == 403
            assert alice.get(paths[2]).json()["review_digest"] == review_digest
            assert alice.get(paths[3]).json()["state"] == run_state
            assert review["digest"] in alice.get(paths[1]).text
            denied: tuple[tuple[str, dict[str, Any] | None], ...] = (
                (
                    base + "/social/creation-reviews",
                    {
                        "configuration_review_id": review["id"],
                        "expected_configuration_digest": review["digest"],
                        "mandate_id": binding.mandate_id,
                        "mandate_revision": binding.revision,
                    },
                ),
                (
                    base + "/reviews/" + source.ids.review_id + "/approval",
                    {
                        "review_digest": review_digest,
                        "plan_digest": source.ids.plan_digest,
                    },
                ),
                (base + "/reviews/" + source.ids.review_id + "/runs", None),
                (base + "/runs/" + source.ids.run_id + "/advance", None),
                (
                    base + "/activation-reviews",
                    {
                        "parent_run_id": source.ids.run_id,
                        "mandate_id": binding.mandate_id,
                        "mandate_revision": binding.revision,
                    },
                ),
            )
            for client in (alice, bob):
                client.app.dependency_overrides[get_media_store] = forbidden
                client.app.dependency_overrides[get_customer_execution_runtime] = forbidden
            before = graph(source.engine)
            for path, valid in denied:
                response = (
                    alice.post(path, headers=headers)
                    if valid is None
                    else alice.post(path, headers=headers, json=valid)
                )
                assert response.status_code == 409, response.text
                assert response.json()["detail"] == "advertising_writes_disabled_in_planning_mvp"
                assert alice.post(path, json={}).status_code == 403
                assert bob.post(path, headers=foreign_headers, json={}).status_code == 404
                extra = alice.post(path, headers=headers, json={"plan": "untrusted extra"})
                assert extra.status_code == 409
                assert extra.json()["detail"] == "advertising_writes_disabled_in_planning_mvp"
                assert graph(source.engine) == before
            assert calls == [] and source.ids.native_posts == 0
            evidence.logout(alice, headers)
            for path in paths:
                assert alice.get(path).status_code == 401
                assert bob.get(path).status_code == 403
            actual = graph(source.engine)
            assert evidence.original is not None
            evidence.assert_delta(evidence.original, actual)
            with pytest.raises(AssertionError):
                evidence.logout(alice, headers)
            altered_logout = deepcopy(actual)
            assert evidence.logout_bounds is not None
            next(
                row
                for row in altered_logout["customer_sessions"]
                if row["digest"] == evidence.alice_session
            )["revoked_at"] = evidence.logout_bounds[0] - 1
            with pytest.raises(AssertionError):
                evidence.assert_delta(evidence.original, altered_logout)
            altered = deepcopy(evidence.original)
            altered["customer_users"][0]["issuer"] = "wrong-original"
            with pytest.raises(AssertionError):
                evidence.assert_delta(altered, actual)
            for table in (
                "customer_sessions",
                "customer_social_configuration_reviews",
                "customer_social_configuration_approvals",
            ):
                altered = deepcopy(actual)
                altered[table].append(deepcopy(altered[table][0]))
                with pytest.raises(AssertionError):
                    evidence.assert_delta(evidence.original, altered)
        finally:
            try:
                alice.close()
            finally:
                bob.close()
