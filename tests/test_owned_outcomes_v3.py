"""Actual owned DB receipt defaults plus explicitly synthetic qualified facts."""

from datetime import date, timedelta
from decimal import Decimal, localcontext
from pathlib import Path

import pytest
from app.goals.models import Goal
from app.outcomes.maturity import (
    IndependentObservation,
    IndependentReconciliationEvidence,
    MaturityContext,
    OperationalMaturityPolicy,
    ReconciledDay,
)
from app.outcomes.models import ActionOutcomeAssessment
from app.outcomes.owned_v3 import (
    OwnedV3Request,
    _snapshot,
    assess_owned_v3,
    compare_owned_v3,
)
from app.publication.service import owner
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_owned_outcomes import evidence
from tests.test_shopify_sales import configuration as configuration


def policy(context: MaturityContext) -> OperationalMaturityPolicy:
    return OperationalMaturityPolicy(
        policy_id="synthetic_fixture",
        version=1,
        metric_definition_digest=context.scope.metric_definition_digest,
        currency=context.scope.currency,
        time_zone=context.scope.time_zone,
        allowed_assurance=("independent_full_window",),
        minimum_age_seconds=0,
        minimum_observations=2,
        minimum_spacing_seconds=1,
        maximum_source_age_seconds=86400,
        maximum_day_revision_micros=0,
    )


def facts(
    context: MaturityContext, start: date, end: date, value: int = 10
) -> IndependentReconciliationEvidence:
    return IndependentReconciliationEvidence(
        environment="contract_test",
        scope=context.scope,
        start=start,
        end=end,
        truncated=False,
        unreadable_observations=0,
        observations=tuple(
            IndependentObservation(
                completion_digest=str(index) * 64,
                observed_at=NOW - timedelta(hours=2 - index),
                fresh_through=NOW - timedelta(hours=2 - index),
                correction_state="settled_as_of",
                days=tuple(
                    ReconciledDay(
                        day=start + timedelta(days=i),
                        state="complete",
                        value_micros=value,
                        entry_count=1,
                    )
                    for i in range((end - start).days)
                ),
            )
            for index in (1, 2)
        ),
    )


def test_actual_receipt_is_insufficient_and_v2_storage_unchanged(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
    with Session(customer_engine) as db:
        wid, actor, body, _, _ = evidence(db, configuration, tmp_path)
    request = OwnedV3Request.model_validate(body.model_dump(exclude={"policy_id"}))
    sessions = sessionmaker(customer_engine)
    report = assess_owned_v3(
        sessions, wid, actor, request, lambda db: owner(db, wid, actor), lambda: NOW
    )
    assert report.status == "insufficient"
    assert {
        "maturity_policy_unavailable",
        "independent_producer_unavailable",
        "effective_time_unknown",
    } <= set(report.reasons)
    assert report.absolute_difference_micros is None and report.recommendation_update is None
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ActionOutcomeAssessment)) == 0
    with pytest.raises(HTTPException):
        assess_owned_v3(
            sessions, wid + 100, actor, request, lambda db: owner(db, wid + 100, actor), lambda: NOW
        )


def test_synthetic_qualified_association_exact_arithmetic_and_timing_guards(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
    with Session(customer_engine) as db:
        wid, actor, body, _, _ = evidence(db, configuration, tmp_path)
        request = OwnedV3Request.model_validate(body.model_dump(exclude={"policy_id"}))
        snapshot = _snapshot(db, wid, actor, request, lambda db: owner(db, wid, actor), lambda: NOW)
    before = facts(snapshot.context, request.before_start, request.before_end)
    after = facts(snapshot.context, request.after_start, request.after_end, 15)
    from app.outcomes.contracts import Window

    boundary = Window.local(
        request.before_start, request.before_end, snapshot.context.scope.time_zone
    ).end_utc
    # Only this explicit synthetic test supplies timing; actual adapters still do not.
    receipt = snapshot.receipt.model_copy(
        update={
            "purpose": "activate",
            "outcome": "verified_effect",
            "dispatched_at": boundary,
            "observed_at": boundary + timedelta(minutes=1),
            "effective_time_evidence": "authoritative_interval",
            "effective_lower": boundary,
            "effective_upper": boundary,
        }
    )
    snapshot = snapshot.model_copy(update={"receipt": receipt})
    with localcontext() as ctx:
        ctx.prec = 2
        report = compare_owned_v3(snapshot, request, policy(snapshot.context), before, after)
    assert report.status == "operational_association_as_of"
    assert report.absolute_difference_micros == 70 and report.relative_difference == Decimal("0.5")
    assert report.causal_lift is None and report.spending_authority == "none"
    with localcontext() as ctx:
        ctx.prec = 2
        huge = compare_owned_v3(
            snapshot,
            request,
            policy(snapshot.context),
            facts(snapshot.context, request.before_start, request.before_end, 10**80),
            facts(snapshot.context, request.after_start, request.after_end, 10**80 + 5),
        )
    assert huge.absolute_difference_micros == 70
    for baseline in (0, -10):
        zero = compare_owned_v3(
            snapshot,
            request,
            policy(snapshot.context),
            facts(snapshot.context, request.before_start, request.before_end, baseline),
            after,
        )
        assert zero.status == "operational_association_as_of" and zero.relative_difference is None
        assert ("baseline_zero" if baseline == 0 else "baseline_negative") in zero.warnings
    overlap = receipt.model_copy(update={"effective_upper": boundary + timedelta(seconds=1)})
    bad = compare_owned_v3(
        snapshot.model_copy(update={"receipt": overlap}),
        request,
        policy(snapshot.context),
        before,
        after,
    )
    assert bad.status == "insufficient" and "windows_overlap_effect_interval" in bad.reasons
    missing = receipt.model_copy(
        update={
            "effective_time_evidence": "unavailable",
            "effective_lower": None,
            "effective_upper": None,
        }
    )
    bad = compare_owned_v3(
        snapshot.model_copy(update={"receipt": missing}),
        request,
        policy(snapshot.context),
        before,
        after,
    )
    assert "effective_time_unknown" in bad.reasons and bad.absolute_difference_micros is None


@pytest.mark.parametrize("change", ["goal", "privacy", "account", "session", "receipt"])
def test_producer_runs_outside_locks_and_changes_are_rejected(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    change: str,
) -> None:
    with Session(customer_engine) as db:
        wid, actor, body, runtime, server = evidence(db, configuration, tmp_path)
    request = OwnedV3Request.model_validate(body.model_dump(exclude={"policy_id"}))
    sessions = sessionmaker(customer_engine)
    calls: list[bool] = []

    def producer(
        context: MaturityContext, start: date, end: date
    ) -> IndependentReconciliationEvidence:
        if not calls:
            with sessions() as db:
                if db.get_bind().dialect.name == "postgresql":
                    from sqlalchemy import text

                    db.execute(text("SET LOCAL lock_timeout = '1000ms'"))
                from app.commerce.evidence import lock_workspace

                lock_workspace(db, wid, active=True)
                goal = db.scalar(
                    select(Goal).where(Goal.id == context.scope.goal_id).with_for_update()
                )
                assert goal
                if change == "goal":
                    goal.revision += 1
                elif change == "privacy":
                    from app.shopify.privacy import process_event

                    from tests.test_shopify_sales import SHOP

                    process_event(db, configuration, "orders/delete", SHOP, {"id": 1}, NOW)
                elif change == "account":
                    from app.google_connections.models import GoogleCustomerConnection

                    native = db.scalar(
                        select(GoogleCustomerConnection).where(
                            GoogleCustomerConnection.workspace_id == wid
                        )
                    )
                    assert native
                    native.status = "disconnected"
                db.commit()
                if change == "receipt":
                    from app.publication import coordinator

                    server.absent = True
                    coordinator.reconcile_attempt(db, wid, body.attempt_id, runtime, lambda: NOW)
        calls.append(True)
        return facts(context, start, end)

    def authorize(db: Session) -> None:
        owner(db, wid, actor)
        if change == "session" and calls:
            raise HTTPException(401, "session revoked")

    with pytest.raises(HTTPException) as error:
        assess_owned_v3(
            sessions,
            wid,
            actor,
            request,
            authorize,
            lambda: NOW,
            policies=lambda scope: policy(
                MaturityContext(
                    environment="contract_test", scope=scope, evaluated_at=NOW, source_current=True
                )
            ),
            producers=lambda _: producer,
        )
    assert (
        error.value.status_code
        == {"goal": 409, "privacy": 404, "account": 409, "session": 401, "receipt": 409}[change]
    )
    assert calls == [True, True]
