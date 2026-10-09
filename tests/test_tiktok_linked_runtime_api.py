from pathlib import Path
from typing import Any

import pytest
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionReceipt,
    ProviderExecutionReview,
    ProviderExposureReservation,
)
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.current_runtime_read_contexts import current_tiktok_source as current_tiktok_source
from tests.test_campaign_video import encoded as encoded
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration
from tests.tiktok_linked_runtime_fixture import configured_linked_customer


@pytest.mark.parametrize(
    "scenario", ["complete", "unknown_creation", "unknown_activation", "media", "confirmation"]
)
def test_configured_linked_creation_then_separate_activation(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    scenario: str,
    encoded: Any,
) -> None:
    alice, base, policy_body, draft, revision, server, requests, control = (
        configured_linked_customer(
            customer_engine, configuration, tmp_path, monkeypatch, replicas, encoded()
        )
    )
    with Session(customer_engine) as db:
        for model in (
            ProviderExecutionReview,
            ProviderExecutionReceipt,
            ProviderExecutionAttempt,
            ProviderExposureReservation,
        ):
            assert db.scalar(select(func.count()).select_from(model)) == 0

    def post(path: str, body: Any = None, expected: int = 200) -> Any:
        response = alice.post(base + path, json=body, headers=headers(alice))
        assert response.status_code == expected, response.text
        assert control["opened"] == control["closed"]
        return response.json()

    policy = post("/mandates", policy_body, 201)
    post(
        f"/mandates/{policy['id']}/consent",
        {"expected_revision": policy["revision"], "policy_digest": policy["policy_digest"]},
    )
    catalog = post("/tiktok/linked/options", {"draft_id": draft, "draft_revision": revision})
    config = post(
        "/tiktok/linked/reviews",
        {
            "draft_id": draft,
            "draft_revision": revision,
            "option_id": catalog["options"][0]["id"],
            "answer": {
                "kind": "tiktok_linked_push",
                "reviewed_video_and_cover": True,
                "commercial_music_rights_reviewed": True,
                "creates_new_linked_post_reviewed": True,
                "ads_only_visibility_reviewed": True,
            },
            "cover_media_id": control["cover_id"],
        },
        201,
    )
    from datetime import timedelta

    control["now"] += timedelta(seconds=10)
    post(
        f"/tiktok/linked/reviews/{config['id']}/confirmation",
        {"expected_digest": config["digest"], "acknowledged": True},
    )
    reviewed = post(
        "/tiktok/linked/creation-reviews",
        {
            "configuration_review_id": config["id"],
            "expected_configuration_digest": config["digest"],
            "mandate_id": policy["id"],
            "mandate_revision": policy["revision"],
        },
        201,
    )
    run: dict[str, Any] = {}
    for activation in (False, True):
        if activation:
            if scenario in {"media", "confirmation"}:
                from app.campaign_review.models import MediaObject
                from app.publication.social_review_models import SocialConfigurationApproval

                with Session(customer_engine) as db:
                    original = db.scalar(select(ProviderExposureReservation))
                    assert original and original.state == "held"
                    original_id = original.id
                    if scenario == "media":
                        cover = db.get(MediaObject, control["cover_id"])
                        assert cover
                        (tmp_path / str(cover.workspace_id) / cover.sha256).unlink()
                    else:
                        confirmation = db.get(SocialConfigurationApproval, config["id"])
                        assert confirmation
                        db.delete(confirmation)
                        db.commit()
                denied = alice.post(
                    base + "/activation-reviews",
                    headers=headers(alice),
                    json={
                        "parent_run_id": run["id"],
                        "mandate_id": policy["id"],
                        "mandate_revision": policy["revision"],
                    },
                )
                assert denied.status_code in {409, 503}, denied.text
                assert server.activations == 0 and control["opened"] == control["closed"]
                with Session(customer_engine) as db:
                    hold = db.get(ProviderExposureReservation, original_id)
                    assert hold and hold.state == "held"
                    assert (
                        db.scalar(select(func.count()).select_from(ProviderExposureReservation))
                        == 1
                    )
                return
            reviewed = post(
                "/activation-reviews",
                {
                    "parent_run_id": run["id"],
                    "mandate_id": policy["id"],
                    "mandate_revision": policy["revision"],
                },
                201,
            )
        post(
            f"/reviews/{reviewed['id']}/approval",
            {"review_digest": reviewed["review_digest"], "plan_digest": reviewed["plan_digest"]},
        )
        run = post(f"/reviews/{reviewed['id']}/runs", expected=201)
        if scenario == "unknown_creation":
            server.timeout = True
            result = post(f"/runs/{run['id']}/advance")
            assert result["state"] == "unknown", result
            writes = server.posts
            server.timeout = False
            repeated = post(f"/runs/{run['id']}/advance")
            assert repeated["state"] == "unknown", repeated
            original_attempt = next(s["attempt_id"] for s in result["steps"] if s["attempt_id"])
            reconciled = post(f"/runs/{run['id']}/reconcile", {"attempt_id": original_attempt})
            assert reconciled["state"] == "unknown", reconciled
            assert [s["attempt_id"] for s in reconciled["steps"] if s["attempt_id"]] == [
                original_attempt
            ]
            assert server.posts == writes == 1
            with Session(customer_engine) as db:
                assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 1
                assert db.scalar(select(func.count()).select_from(ProviderExposureReservation)) == 1
                reservation = db.scalar(select(ProviderExposureReservation))
                assert reservation and reservation.state == "held"
            return
        if activation and scenario == "unknown_activation":
            server.activation_timeout = True
            server.delay = True
            first = post(f"/runs/{run['id']}/advance")
            assert first["state"] == "unknown", first
            server.activation_timeout = False
            repeated = post(f"/runs/{run['id']}/advance")
            assert repeated["state"] == "unknown", repeated
            original_attempt = next(s["attempt_id"] for s in first["steps"] if s["attempt_id"])
            reconciled = post(f"/runs/{run['id']}/reconcile", {"attempt_id": original_attempt})
            assert reconciled["state"] == "unknown", reconciled
            assert [s["attempt_id"] for s in reconciled["steps"] if s["attempt_id"]] == [
                original_attempt
            ]
            assert server.activations == 1
            with Session(customer_engine) as db:
                assert db.scalar(select(func.count()).select_from(ProviderExposureReservation)) == 1
            return
        expected_state = "activation_observed" if activation else "created_paused"
        for _ in range(30):
            run = post(f"/runs/{run['id']}/advance")
            assert run["state"] != "unknown", run
            if run["state"] == expected_state:
                break
        assert run["state"] == expected_state
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderExposureReservation)) == 1
        row = db.scalar(select(ProviderExposureReservation))
        assert row and row.state == "held"
    assert server.posts > 0 and server.activations > 0 and requests


@pytest.mark.parametrize("change", ["permission", "session", "source", "rights"])
@pytest.mark.planning_boundary
def test_configured_linked_confirmation_rechecks_owned_current_facts(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    encoded: Any,
    change: str,
    current_tiktok_source: Any,
) -> None:
    from tests.tiktok_linked_current_read_fixture import configured_linked_customer

    customer_engine, tmp_path, replicas, ids = current_tiktok_source

    import time
    from datetime import timedelta

    from app.customers.access import SESSION_COOKIE, digest
    from app.customers.models import CustomerSession
    from app.sources.models import SourceConnection

    alice, base, _, draft, revision, server, _, control = configured_linked_customer(
        customer_engine, configuration, tmp_path, monkeypatch, replicas, ids
    )
    prefix = base + "/tiktok/linked"
    response = alice.post(
        prefix + "/options",
        json={"draft_id": draft, "draft_revision": revision},
        headers=headers(alice),
    )
    assert response.status_code == 200, response.text
    option = response.json()["options"][0]
    intent = dict(
        draft_id=draft,
        draft_revision=revision,
        option_id=option["id"],
        cover_media_id=control["cover_id"],
        answer=dict(
            kind="tiktok_linked_push",
            reviewed_video_and_cover=True,
            commercial_music_rights_reviewed=True,
            creates_new_linked_post_reviewed=True,
            ads_only_visibility_reviewed=True,
        ),
    )
    if change == "rights":
        intent["answer"]["commercial_music_rights_reviewed"] = False
    prepared = alice.post(prefix + "/reviews", json=intent, headers=headers(alice))
    if change == "rights":
        assert prepared.status_code == 422
    else:
        assert prepared.status_code == 201, prepared.text
        saved = prepared.json()
        assert saved["identity_label"] == option["name"]
        assert saved["media"]["cover"]["media_id"] == control["cover_id"]
        assert saved["financial_qualification"] == "not_assessed"
        if change == "permission":
            control["can_push"] = False
        else:

            def revoke() -> None:
                with Session(customer_engine) as db:
                    if change == "session":
                        session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
                        assert session
                        session.revoked_at = int(time.time())
                    else:
                        source = db.scalar(
                            select(SourceConnection).where(
                                SourceConnection.provider == "tiktok_ads"
                            )
                        )
                        assert source
                        source.generation += 1
                    db.commit()

            control["discovery_callback"] = revoke
        control["now"] += timedelta(seconds=15)
        denied = alice.post(
            prefix + f"/reviews/{saved['id']}/confirmation",
            json={"expected_digest": saved["digest"], "acknowledged": True},
            headers=headers(alice),
        )
        assert denied.status_code in {401, 409, 503}, denied.text
    with Session(customer_engine) as db:
        from app.publication.social_review_models import SocialConfigurationApproval

        for model in (
            SocialConfigurationApproval,
            ProviderExecutionReview,
            ProviderExecutionAttempt,
            ProviderExposureReservation,
        ):
            assert db.scalar(select(func.count()).select_from(model)) == 0
    assert server.posts == server.activations == 0
