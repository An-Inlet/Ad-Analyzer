"""Actual configured API/job worker with native HTTP mocks, no seeded candidates."""

from pathlib import Path
from typing import Any

import pytest
from app.jobs.customer_runtime import run_customer_tick
from app.optimization_candidates.models import CandidateJob, CandidateResult
from app.publication.execution_models import ProviderExecutionAttempt, ProviderExposureReservation
from app.settings import Settings, settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.configured_candidates_fixture import configured_candidates_customer
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("platform", ["google_ads", "meta_ads"])
@pytest.mark.parametrize("mode", ["unqualified", "scenario", "revoked", "revoked_during_read"])
def retained_test_configured_candidate_api_and_actual_tick(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    platform: str,
    mode: str,
) -> None:
    alice, base, wire, control, draft = configured_candidates_customer(
        customer_engine, configuration, tmp_path, monkeypatch, replicas, platform, mode
    )
    endpoint = base + "/candidates"
    capability = alice.get(endpoint + "/capabilities")
    assert capability.status_code == 200 and capability.json()["configured"], capability.text
    response = alice.post(
        endpoint + "/reads",
        headers=headers(alice),
        json=dict(
            mandate_id=draft["mandate_id"],
            mandate_revision=draft["revision"],
            policy=dict(policy_id="a" * 32, revision=1),
        ),
    )
    assert response.status_code == 201, response.text
    assert len(response.json()["job_ids"]) == 1, response.text
    job_id = response.json()["job_ids"][0]
    if mode == "revoked":
        from app.customers.access import SESSION_COOKIE, digest
        from app.customers.models import CustomerSession

        with Session(customer_engine) as db:
            session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
            assert session
            session.revoked_at = int(control["now"].timestamp())
            db.commit()
    if mode == "revoked_during_read":

        def revoke() -> None:
            from app.customers.access import SESSION_COOKIE, digest
            from app.customers.models import CustomerSession

            with Session(customer_engine) as db:
                original = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
                assert original
                original.revoked_at = int(control["now"].timestamp())
                db.commit()

        control["callback"] = revoke
    outcomes = run_customer_tick(customer_engine, configuration=settings, now=control["now"])
    assert outcomes["candidate_reads"] == "completed"
    if mode in {"revoked", "revoked_during_read"}:
        with Session(customer_engine) as db:
            assert db.scalar(select(func.count()).select_from(CandidateResult)) == 0
        assert not wire.google.writes and not wire.meta.posts
        assert control["opened"] == control["closed"]
        return
    status = alice.get(endpoint + "/reads/" + job_id)
    assert status.status_code == 200, status.text
    assert status.json()["state"] == "completed", status.text
    assert status.json()["decision"]["status"] == (
        "suggested" if mode == "scenario" else "blocked"
    ), status.text
    assert status.json()["decision"]["evidence"]["qualification"] == (
        "contract_scenario" if mode == "scenario" else "unqualified"
    )
    from app.optimization_candidates.contracts import CandidateDecision
    from app.optimization_candidates.customer_contracts import CandidateReadStatus
    from pydantic import ValidationError

    assert status.json()["decision_digest"] == CandidateDecision.model_validate(
        status.json()["decision"]
    ).digest()
    with pytest.raises(ValidationError):
        CandidateReadStatus.model_validate({**status.json(), "decision_digest": "0" * 64})
    if mode == "scenario":

        result = status.json()
        review = alice.post(
            endpoint + f"/results/{result['result_id']}/review",
            headers=headers(alice),
            json={
                "result_id": result["result_id"],
                "expected_decision_digest": result["decision_digest"],
            },
        )
        assert review.status_code == 200, review.text
        reviewed = review.json()
        approval = alice.post(
            base + f"/reviews/{reviewed['review_id']}/approval",
            headers=headers(alice),
            json={
                "review_digest": reviewed["review_digest"],
                "plan_digest": reviewed["plan_digest"],
            },
        )
        assert approval.status_code == 200, approval.text
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(CandidateJob)) == 1
        assert db.scalar(select(func.count()).select_from(CandidateResult)) == 1
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
        assert db.scalar(select(func.count()).select_from(ProviderExposureReservation)) == 0
    assert not wire.google.writes and not wire.meta.posts
    assert control["opened"] == control["closed"]
