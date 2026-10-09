"""Owned snapshot orchestration over actual API-adapter receipts and DB fences.

Only qualified effect/timing/reconciliation/policy values are explicit synthetic fixtures.
"""

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from app.commerce.models import CommerceMeasurementPublication
from app.commerce.sync import CommerceSyncService
from app.outcome_feedback import service
from app.outcome_feedback.models import ContributionSlot, V3EvidenceDependency
from app.outcome_feedback.snapshot import apply_owned_feedback, read_feedback_snapshot
from app.outcomes.contracts import Window
from app.outcomes.owned_v3 import OwnedSnapshot, OwnedV3Request, _snapshot, compare_owned_v3
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from tests.feedback_snapshot_retained_fixture import (
    snapshot_receipt_source as snapshot_receipt_source,
)
from tests.test_commerce_measurement import NOW, FakeMeasurement, source
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_feedback_policy import policy
from tests.test_optimization_candidates import fixture
from tests.test_owned_outcomes_v3 import facts
from tests.test_owned_outcomes_v3 import policy as maturity_policy
from tests.test_shopify_sales import configuration as configuration


def prepare(
    db: Session,
    config: Settings,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    after_value: int = 15,
) -> Any:
    principal, work, _, _, runtime, _ = fixture(db, config, path, with_receipt=True)
    actor = principal.user.id
    wid = work.scope.account.workspace_id
    later = NOW + timedelta(hours=1)
    CommerceSyncService(
        db, config, FakeMeasurement(config, [([source(updated=later)], None)])
    ).page(wid, now=later)
    pubs = list(
        db.scalars(
            select(CommerceMeasurementPublication)
            .where(CommerceMeasurementPublication.workspace_id == wid)
            .order_by(CommerceMeasurementPublication.publication_revision)
        )
    )
    assert work.scope.source.attempt_id
    request = OwnedV3Request(
        attempt_id=work.scope.source.attempt_id,
        publication_id=pubs[-1].id,
        before_start=date(2026, 9, 1),
        before_end=date(2026, 9, 15),
        after_start=date(2026, 9, 15),
        after_end=date(2026, 9, 29),
    )
    from app.optimization_candidates.service import authorize as owned_authorize

    def authorize(session: Session) -> None:
        owned_authorize(session, principal, wid, runtime)

    original = _snapshot

    def synthetic(*args: Any, **kwargs: Any) -> OwnedSnapshot:
        snap = original(*args, **kwargs)
        boundary = Window.local(
            request.before_start, request.before_end, snap.context.scope.time_zone
        ).end_utc
        return snap.model_copy(
            update={
                "receipt": snap.receipt.model_copy(
                    update={
                        "outcome": "verified_effect",
                        "effective_time_evidence": "authoritative_interval",
                        "effective_lower": boundary,
                        "effective_upper": boundary,
                        "dispatched_at": boundary,
                        "observed_at": boundary,
                    }
                )
            }
        )

    monkeypatch.setattr(service, "_snapshot", synthetic)
    snap = synthetic(db, wid, actor, request, authorize, lambda: later)
    mature = maturity_policy(snap.context)

    def independent(start: date, end: date, value: int) -> Any:
        data = facts(snap.context, start, end, value)
        return data.model_copy(
            update={
                "observations": tuple(
                    item.model_copy(
                        update={
                            "completion_digest": pub.completion_digest,
                            "observed_at": pub.published_at.replace(tzinfo=NOW.tzinfo),
                            "fresh_through": pub.source_window_end.replace(tzinfo=NOW.tzinfo),
                        }
                    )
                    for item, pub in zip(data.observations, pubs, strict=True)
                )
            }
        )

    value = compare_owned_v3(
        snap,
        request,
        mature,
        independent(request.before_start, request.before_end, 10),
        independent(request.after_start, request.after_end, after_value),
    )
    assert value.status == "operational_association_as_of", value.reasons
    row = service.persist_assessment(
        db,
        wid,
        actor,
        value,
        tuple(
            service.EvidenceReference(
                publication_id=p.id,
                manifest_digest=p.manifest_digest,
                completion_digest=p.completion_digest,
            )
            for p in pubs
        ),
        authorize,
        lambda: later,
        policies=lambda _: mature,
    )
    db.commit()
    return wid, actor, row.id, value, authorize, later, mature, principal


@pytest.mark.planning_boundary
def test_owned_snapshot_default_empty_active_replay_retraction(
    snapshot_receipt_source: Engine,
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    customer_engine = snapshot_receipt_source
    with Session(customer_engine) as db:
        wid, actor, saved, value, authorize, later, mature, _ = prepare(
            db, configuration, tmp_path, monkeypatch
        )
        chosen = policy(value)
        kwargs: dict[str, Any] = dict(policies=lambda _: mature, decisions=lambda _: chosen)

        def read(**extra: Any) -> Any:
            return read_feedback_snapshot(
                db, wid, actor, saved, chosen.family, authorize, lambda: later, **(kwargs | extra)
            )

        missing = read(decisions=lambda _: None)
        assert (
            missing.status == "unavailable" and missing.score is None and not missing.contributions
        )
        assert read().status == "empty" and read().score is None
        scope, slot = apply_owned_feedback(
            db, wid, actor, saved, chosen.family, None, authorize, lambda: later, **kwargs
        )
        assert slot and scope == missing.scope
        first = read()
        assert first.status == "available" and first.score == Decimal("0.2")
        assert len(first.contributions) == 1 and first.contributions[0].revision == 1
        assert first.count_interpretation == "active_contributions_not_independent_observations"
        assert read().snapshot_digest == first.snapshot_digest
        _, replay = apply_owned_feedback(
            db, wid, actor, saved, chosen.family, None, authorize, lambda: later, **kwargs
        )
        assert replay and replay.id == slot.id and read().snapshot_digest == first.snapshot_digest
        with pytest.raises(HTTPException):
            read(expected_scope=scope.model_copy(update={"target_digest": "0" * 64}))
        db.execute(delete(ContributionSlot).where(ContributionSlot.id == slot.id))
        db.flush()
        assert read().status == "empty" and read().score is None
        db.execute(delete(V3EvidenceDependency).where(V3EvidenceDependency.assessment_id == saved))
        with pytest.raises(HTTPException):
            read()


@pytest.mark.planning_boundary
def test_current_session_and_original_plan_required(
    snapshot_receipt_source: Engine,
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    customer_engine = snapshot_receipt_source
    from app.publication.execution_models import ProviderExecutionReview, ProviderExecutionRun

    with Session(customer_engine) as db:
        wid, actor, saved, value, authorize, later, mature, principal = prepare(
            db, configuration, tmp_path, monkeypatch
        )
        chosen = policy(value)

        def read() -> Any:
            return read_feedback_snapshot(
                db,
                wid,
                actor,
                saved,
                chosen.family,
                authorize,
                lambda: later,
                policies=lambda _: mature,
                decisions=lambda _: chosen,
            )

        assert read().status == "empty"
        run = db.get(ProviderExecutionRun, value.receipt.run_id)
        assert run
        review = db.get(ProviderExecutionReview, run.review_id)
        assert review
        old = review.plan_digest
        review.plan_digest = "0" * 64
        db.flush()
        with pytest.raises(HTTPException):
            read()
        review.plan_digest = old
        db.flush()
        principal.session.revoked_at = int(later.timestamp())
        db.flush()
        with pytest.raises(HTTPException):
            read()


@pytest.mark.planning_boundary
def test_zero_signal_is_not_empty_and_policy_race_rejects(
    snapshot_receipt_source: Engine,
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    customer_engine = snapshot_receipt_source
    with Session(customer_engine) as db:
        wid, actor, saved, value, authorize, later, mature, _ = prepare(
            db, configuration, tmp_path, monkeypatch, after_value=10
        )
        chosen = policy(value).model_copy(update={"minimum_absolute_relative_signal": Decimal(0)})
        kwargs: dict[str, Any] = dict(policies=lambda _: mature, decisions=lambda _: chosen)
        scope, slot = apply_owned_feedback(
            db, wid, actor, saved, chosen.family, None, authorize, lambda: later, **kwargs
        )
        assert slot
        result = read_feedback_snapshot(
            db, wid, actor, saved, chosen.family, authorize, lambda: later, **kwargs
        )
        assert result.status == "available" and result.score == 0 and len(result.contributions) == 1
        calls = 0

        def changing(_: str) -> Any:
            nonlocal calls
            calls += 1
            return chosen if calls == 1 else chosen.model_copy(update={"version": 2})

        with pytest.raises(HTTPException, match="policy changed during read"):
            read_feedback_snapshot(
                db,
                wid,
                actor,
                saved,
                chosen.family,
                authorize,
                lambda: later,
                policies=lambda _: mature,
                decisions=changing,
            )
        with pytest.raises(HTTPException):
            read_feedback_snapshot(
                db, wid + 999, actor, saved, chosen.family, authorize, lambda: later, **kwargs
            )


@pytest.mark.planning_boundary
def test_actual_unqualified_receipt_and_source_do_not_create_feedback(
    snapshot_receipt_source: Engine,
    customer_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    customer_engine = snapshot_receipt_source
    from app.optimization_candidates.service import authorize as owned_authorize

    with Session(customer_engine) as db:
        principal, work, _, _, runtime, _ = fixture(db, configuration, tmp_path, with_receipt=True)
        wid, actor = work.scope.account.workspace_id, principal.user.id
        assert work.scope.source.attempt_id
        request = OwnedV3Request(
            attempt_id=work.scope.source.attempt_id,
            publication_id=work.scope.source.publication_id,
            before_start=date(2026, 9, 1),
            before_end=date(2026, 9, 15),
            after_start=date(2026, 9, 15),
            after_end=date(2026, 9, 29),
        )

        def authorize(session: Session) -> None:
            owned_authorize(session, principal, wid, runtime)

        snap = _snapshot(db, wid, actor, request, authorize, lambda: NOW)
        value = compare_owned_v3(snap, request, None, None, None)
        assert value.status == "insufficient"
        pub = db.get(CommerceMeasurementPublication, value.publication_id)
        assert pub
        row = service.persist_assessment(
            db,
            wid,
            actor,
            value,
            (
                service.EvidenceReference(
                    publication_id=pub.id,
                    manifest_digest=pub.manifest_digest,
                    completion_digest=pub.completion_digest,
                ),
            ),
            authorize,
            lambda: NOW,
        )
        chosen = policy(value)
        _, slot = apply_owned_feedback(
            db,
            wid,
            actor,
            row.id,
            chosen.family,
            None,
            authorize,
            lambda: NOW,
            decisions=lambda _: chosen,
        )
        assert slot is None
        result = read_feedback_snapshot(
            db, wid, actor, row.id, chosen.family, authorize, lambda: NOW
        )
        assert result.status == "unavailable" and result.score is None
