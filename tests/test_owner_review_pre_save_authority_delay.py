"""Real pre-save final-fact expiry; controlled fault, not a latency benchmark."""

import copy
import hmac
import json
import time
from pathlib import Path
from typing import Any

import pytest
from app.customers.access import SESSION_COOKIE
from app.planning_documents import authority, repository
from app.planning_documents.owner_review_plan_composer import OwnerReviewPlanComposer
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine

from tests.creative_q07_fixture import planning_snapshot
from tests.owner_review_runtime_fixture import configured_owner_review
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_owner_review_runtime_api import generation
from tests.test_owner_review_runtime_authority_delay import _source_snapshot
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def test_v6_real_delay_after_final_refresh_before_save(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    fixture, body, calls, _ = configured_owner_review(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    alice, _, _ = replicas
    original_cookie = alice.cookies[SESSION_COOKIE]
    wid = fixture.basis.workspace_id
    root = f"/api/customer/v1/workspaces/{wid}/planning/plans"
    response = alice.post(root, headers=headers(alice), json=body)
    assert response.status_code == 201, response.text
    plan_id = response.json()["plan_id"]
    before = planning_snapshot(customer_engine), _source_snapshot(customer_engine, wid)
    effects = financial_counts(customer_engine)
    provider_calls = copy.deepcopy(calls), copy.deepcopy(fixture.calls)
    composed: list[bool] = []
    delayed: list[authority.IdentityFact] = []
    save_facts: list[authority.IdentityFact] = []
    original_errors: list[HTTPException] = []
    original_compose = OwnerReviewPlanComposer.compose
    original_refresh = authority.refresh
    original_save = repository.save_generation
    original_lock = authority.lock

    def compose(self: OwnerReviewPlanComposer, **kwargs: Any) -> Any:
        result = original_compose(self, **kwargs)
        assert result.policy_version == "inlet.descriptive-review.v6"
        assert result.inputs.plan_id == plan_id and not composed
        composed.append(True)
        return result

    def refresh(*args: Any, **kwargs: Any) -> authority.IdentityFact:
        fact = original_refresh(*args, **kwargs)
        if composed:
            already_delayed = bool(delayed)
            assert not already_delayed, "unexpected refresh after final composition"
            delayed.append(fact)
            time.sleep(6)  # One real wait; original completed_monotonic is untouched.
        return fact

    def lock(*args: Any, **kwargs: Any) -> Any:
        try:
            return original_lock(*args, **kwargs)
        except HTTPException as error:
            if delayed:
                assert error.status_code == 409 and error.detail == "planning_authority_expired"
                original_errors.append(error)
            raise

    def save(*args: Any, **kwargs: Any) -> Any:
        ready_for_save = composed == [True] and len(delayed) == 1 and not save_facts
        assert ready_for_save, "final publication marker or save count changed"
        same_fact = kwargs["fact"] is delayed[0]
        assert same_fact, "original final publication fact changed at save"
        save_facts.append(kwargs["fact"])
        try:
            return original_save(*args, **kwargs)
        except HTTPException as error:
            assert len(original_errors) == 1 and error is original_errors[0]
            raise

    monkeypatch.setattr(OwnerReviewPlanComposer, "compose", compose)
    monkeypatch.setattr(authority, "refresh", refresh)
    monkeypatch.setattr(authority, "lock", lock)
    monkeypatch.setattr(repository, "save_generation", save)
    response = alice.post(root + f"/{plan_id}/generate", headers=headers(alice), json=generation())
    counts_match = (
        composed == [True] and len(delayed) == len(save_facts) == len(original_errors) == 1
    )
    assert counts_match, "expected one composition, delay, save and original refusal"
    same_fact = save_facts[0] is delayed[0]
    assert same_fact, "original final publication fact changed"
    assert response.status_code == 409, response.text
    assert response.json() == {"detail": "planning_authority_expired"}
    records = [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.name == "inlet.planning.authority"
    ]
    assert records == [
        dict(
            event="planning_authority_expired",
            schema_version=1,
            route="generate",
            phase="lock",
            cause="fact_age_outside_window",
            session_predicate="not_evaluated",
            status=409,
        )
    ]
    assert (planning_snapshot(customer_engine), _source_snapshot(customer_engine, wid)) == before
    assert financial_counts(customer_engine) == effects
    assert (calls, fixture.calls) == provider_calls
    same_session = hmac.compare_digest(alice.cookies[SESSION_COOKIE], original_cookie)
    assert same_session, "original authenticated session changed"
