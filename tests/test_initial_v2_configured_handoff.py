"""Actual configured planning to separate-consent exact review; provider HTTP mocked."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from app.customers.access import SESSION_COOKIE, digest
from app.customers.models import CustomerSession
from app.goals.models import Goal
from app.initial_planning import review_v2_bridge
from app.initial_planning.models import PreviewRow
from app.initial_planning.review_models import InitialPreviewReviewLink
from app.initial_planning.review_v2_models import InitialPreviewExecutionProofRow
from app.meta.models import MetaConnection
from app.publication import optimization
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionReview,
    ProviderExposureReservation,
    ProviderPeriodLedger,
)
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import login
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration
from tests.v2_execution_fixture import ready


@pytest.mark.parametrize(
    "mode",
    [
        "verified",
        "unknown",
        "proof_erased",
        "preview_erased",
        "after_claim",
        "different_cap",
        "native_drift",
        "session_during_prepare",
        "goal_during_prepare",
        "source_during_prepare",
        "tampered_digest",
        "atomic_rollback",
        "other_original_session",
    ],
)
def test_actual_v2_separate_consent_and_review(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    mode: str,
) -> None:
    unknown = mode == "unknown"
    alice, root, base, query, preview, server, controls, planning = ready(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
    )
    endpoint = root + "/previews/" + preview["id"]
    unavailable = alice.get(endpoint + "/execution-review-options")
    assert unavailable.status_code == 200, unavailable.text
    assert unavailable.json()["unavailable_reason"] == "separate_execution_consent_required"
    opt = base + "/optimization"
    options = alice.post(opt + "/target-options", json=query, headers=headers(alice))
    assert options.status_code == 200, options.text
    assert len(options.json()["options"]) == 1, options.text
    selected = {**query, "option_id": options.json()["options"][0]["id"]}
    drafted = alice.post(
        opt + "/budget-mandates",
        headers=headers(alice),
        json={
            "intent": {
                "selection": selected,
                "total_cap_micros": 40_000_000 if mode == "different_cap" else 50_000_000,
                "aggressiveness": "balanced",
            }
        },
    )
    assert drafted.status_code == 201, drafted.text
    budget = drafted.json()
    consent = alice.post(
        opt + "/budget-mandates/" + budget["mandate_id"] + "/consent",
        headers=headers(alice),
        json={
            "selection": selected,
            "expected_revision": budget["revision"],
            "policy_digest": budget["policy_digest"],
            "preparation_digest": budget["preparation_digest"],
        },
    )
    assert consent.status_code == 200, consent.text
    choices = alice.get(endpoint + "/execution-review-options")
    assert choices.status_code == 200, choices.text
    assert len(choices.json()["options"]) == (0 if mode == "different_cap" else 1), choices.text
    body = {
        "expected_preview_digest": choices.json()["preview_digest"],
        "mandate_id": budget["mandate_id"],
        "mandate_revision": budget["revision"],
    }
    if mode == "native_drift":
        server.meta_campaign["daily_budget"] = "2000"
    if mode == "session_during_prepare":

        def revoke() -> None:
            with Session(customer_engine) as db:
                original = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
                assert original
                original.revoked_at = int(datetime.now(UTC).timestamp())
                db.commit()

        controls["callback"] = revoke
    if mode == "other_original_session":
        login(alice, "budget-first:second")
    if mode == "tampered_digest":
        body["expected_preview_digest"] = "0" * 64
    if mode in {"goal_during_prepare", "source_during_prepare"}:

        def drift() -> None:
            with Session(customer_engine) as db:
                if mode == "goal_during_prepare":
                    goal = db.scalar(select(Goal))
                    assert goal
                    goal.revision += 1
                else:
                    source = db.scalar(select(MetaConnection))
                    assert source
                    source.generation += 1
                db.commit()

        controls["callback"] = drift
    if mode == "atomic_rollback":

        def failing_guard(*args: Any, **kwargs: Any) -> Any:
            def fail(db: Session, *args: Any) -> None:
                assert db.scalar(select(func.count()).select_from(InitialPreviewReviewLink)) == 1
                assert (
                    db.scalar(select(func.count()).select_from(InitialPreviewExecutionProofRow))
                    == 1
                )
                raise HTTPException(409, "controlled_final_fence_failure")

            return fail

        monkeypatch.setattr(review_v2_bridge, "guard_for", failing_guard)
    response = alice.post(endpoint + "/execution-review", headers=headers(alice), json=body)
    if mode in {
        "different_cap",
        "native_drift",
        "session_during_prepare",
        "goal_during_prepare",
        "source_during_prepare",
        "tampered_digest",
        "atomic_rollback",
        "other_original_session",
    }:
        assert response.status_code in {401, 409}, response.text
        with Session(customer_engine) as db:
            assert db.scalar(select(func.count()).select_from(ProviderExecutionReview)) == 0
            assert db.scalar(select(func.count()).select_from(InitialPreviewReviewLink)) == 0
            assert db.scalar(select(func.count()).select_from(InitialPreviewExecutionProofRow)) == 0
        assert not server.posts
        return
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "review_required"
    assert response.json()["execution_mandate"]["mandate_id"] != planning["mandate_id"]
    repeated = alice.post(endpoint + "/execution-review", headers=headers(alice), json=body)
    assert repeated.status_code == 200 and repeated.json() == response.json(), repeated.text
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderPeriodLedger)) == 1
        assert db.scalar(select(func.count()).select_from(ProviderExecutionReview)) == 1
    reviewed = response.json()
    if mode in {"proof_erased", "preview_erased"}:
        with Session(customer_engine) as db:
            if mode == "proof_erased":
                db.execute(delete(InitialPreviewExecutionProofRow))
            else:
                db.execute(delete(PreviewRow).where(PreviewRow.id == preview["id"]))
            db.commit()
        denied = alice.post(endpoint + "/execution-review", headers=headers(alice), json=body)
        assert denied.status_code == 409, denied.text
        denied = alice.post(
            base + f"/reviews/{reviewed['review_id']}/approval",
            headers=headers(alice),
            json={
                "review_digest": reviewed["review_digest"],
                "plan_digest": reviewed["plan_digest"],
            },
        )
        assert denied.status_code == 409, denied.text
        with Session(customer_engine) as db:
            assert db.scalar(select(func.count()).select_from(ProviderExecutionReview)) == 1
        assert not server.posts
        return
    approval = alice.post(
        base + f"/reviews/{reviewed['review_id']}/approval",
        headers=headers(alice),
        json={
            "review_digest": reviewed["review_digest"],
            "plan_digest": reviewed["plan_digest"],
        },
    )
    assert approval.status_code == 200, approval.text
    run = alice.post(base + f"/reviews/{reviewed['review_id']}/runs", headers=headers(alice))
    assert run.status_code == 201, run.text
    if unknown:
        server.ignore = server.timeout = True
    if mode == "after_claim":
        original_execute = optimization.execute_claim

        def withdrawn(*args: Any, **kwargs: Any) -> Any:
            with Session(customer_engine) as db:
                assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 1
                assert db.scalar(select(ProviderExposureReservation.state)) == "held"
                db.execute(delete(InitialPreviewExecutionProofRow))
                db.commit()
            return original_execute(*args, **kwargs)

        monkeypatch.setattr(optimization, "execute_claim", withdrawn)
    advanced = alice.post(base + f"/runs/{run.json()['id']}/advance", headers=headers(alice))
    if mode == "after_claim":
        assert advanced.status_code == 409, advanced.text
        assert not server.posts
        with Session(customer_engine) as db:
            assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 1
            assert db.scalar(select(ProviderExposureReservation.state)) == "held"
        return
    assert advanced.status_code == 200, advanced.text
    attempt = advanced.json()["steps"][0]["attempt_id"]
    receipt = alice.get(base + f"/attempts/{attempt}/receipt")
    assert receipt.status_code == 200, receipt.text
    assert receipt.json()["receipt"]["outcome"] == (
        "unknown" if unknown else "verified_target_state"
    ), (receipt.text, server.posts)
    replay = alice.post(base + f"/runs/{run.json()['id']}/advance", headers=headers(alice))
    assert replay.status_code == 200, replay.text
    assert len(server.posts) == 1
    if unknown:
        with Session(customer_engine) as db:
            db.execute(delete(InitialPreviewExecutionProofRow))
            db.commit()
        reconciled = alice.post(
            base + f"/runs/{run.json()['id']}/reconcile",
            headers=headers(alice),
            json={"attempt_id": attempt},
        )
        assert reconciled.status_code == 200, reconciled.text
        assert len(server.posts) == 1
        with Session(customer_engine) as db:
            assert db.scalar(select(ProviderExposureReservation.state)) == "held"
