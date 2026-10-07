"""0064 cascade→0068 forward fence, with0066 protected response survival.

The derived numeric graph and its alternate retained-publication dependency are
explicit schema fixtures. They never qualify learning or provider delivery. The
review/session/claim/native adapter/response/reconciliation path is real offline code.
"""

from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from app.commerce.models import CommerceMeasurementPublication
from app.optimization_candidates import review_bridge as bridge
from app.optimization_candidates.models import CandidateJob
from app.optimization_candidates.review_models import CandidateReviewLink
from app.outcome_feedback.models import V3Assessment, V3EvidenceDependency
from app.publication import optimization as optimization
from app.publication.execution_models import (
    GoogleOriginalCompletion,
    ProviderExecutionReceipt,
    ProviderExecutionReview,
    ProviderExposureReservation,
)
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from tests.test_candidate_review_bridge import assembled
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_shopify_sales import configuration as configuration


def derived_graph(db: Session, wid: int, attempt_id: str) -> tuple[str, str]:
    receipt = db.scalar(
        select(ProviderExecutionReceipt).where(ProviderExecutionReceipt.attempt_id == attempt_id)
    )
    if receipt is None:
        # FK-only fixture: no API receipt, step state or source qualification is changed.
        receipt = ProviderExecutionReceipt(
            id=uuid4().hex,
            workspace_id=wid,
            attempt_id=attempt_id,
            sequence=1,
            supersedes_id=None,
            digest="1" * 64,
            receipt={},
            projection={},
            observed_at=NOW,
        )
        db.add(receipt)
        db.flush()
    anchor = db.scalar(
        select(CommerceMeasurementPublication).where(
            CommerceMeasurementPublication.workspace_id == wid
        )
    )
    assert anchor
    # A distinct retained dependency exercises erasure beyond the job's direct anchor.
    copied = {c.name: getattr(anchor, c.name) for c in anchor.__table__.columns}
    copied.update(
        id=uuid4().hex,
        publication_revision=anchor.publication_revision + 1,
        completion_digest="2" * 64,
        manifest_digest="3" * 64,
        # This is a dependency-graph fixture, not a new current v1 source.
        # A higher v1 revision would correctly invalidate the candidate before
        # the intended final-context erasure race is reached.
        manifest={"schema_version": "explicit_historical_dependency_fixture.v1"},
        published_at=NOW - timedelta(days=1),
    )
    historical = CommerceMeasurementPublication(**copied)
    db.add(historical)
    db.flush()
    assessment = V3Assessment(
        id=uuid4().hex,
        workspace_id=wid,
        store_id=anchor.store_id,
        environment="contract_test",
        attempt_id=attempt_id,
        receipt_id=receipt.id,
        receipt_sequence=receipt.sequence,
        generation=anchor.generation,
        privacy_epoch=anchor.privacy_epoch,
        input_digest="4" * 64,
        document_digest="5" * 64,
        document={"explicit_schema_fixture": True, "numeric_value": "123"},
        created_at=NOW,
    )
    db.add(assessment)
    db.flush()
    for ordinal, pub in enumerate((anchor, historical)):
        db.add(
            V3EvidenceDependency(
                assessment_id=assessment.id,
                ordinal=ordinal,
                workspace_id=wid,
                publication_id=pub.id,
                manifest_digest=pub.manifest_digest,
                completion_digest=pub.completion_digest,
            )
        )
    db.commit()
    return assessment.id, historical.id


@pytest.mark.parametrize("stage", ["claimed_final_context", "completed"])
def test_dependency_retraction_blocks_forward_preserves_protected_history(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
) -> None:
    with Session(customer_engine) as db:
        principal, wid, intent, runtime, server = assembled(
            db, configuration, tmp_path, "google_ads", monkeypatch
        )
        actor = principal.user.id
        review = bridge.prepare_candidate_review(db, principal, wid, intent, runtime)
        execution = bridge.bind_execution(runtime, principal)
        optimization.approve_optimization(
            db,
            wid,
            review.review_id,
            review.review_digest,
            review.plan_digest,
            actor,
            execution,
            lambda: NOW,
        )
        run = optimization.create_run(db, wid, review.review_id, actor, execution, lambda: NOW)
        claim = optimization.claim_step(db, wid, run.id, actor, execution, lambda: NOW)
        assert claim
        if stage == "completed":
            assert (
                optimization.execute_claim(db, claim, actor, execution, lambda: NOW).outcome
                == "verified_target_state"
            )
            assert db.get(GoogleOriginalCompletion, claim.attempt_id) is not None
        numeric_id, dependency_id = derived_graph(db, wid, claim.attempt_id)
        holds = [
            (r.id, r.state, r.amount_micros)
            for r in db.scalars(select(ProviderExposureReservation))
        ]
        db.commit()

        if stage == "claimed_final_context":
            optimization.checked_review(
                db, wid, review.review_id, actor, execution, lambda: NOW
            )
            db.rollback()

        def erase() -> None:
            with Session(customer_engine) as other:
                other.execute(
                    delete(CommerceMeasurementPublication).where(
                        CommerceMeasurementPublication.id == dependency_id
                    )
                )
                other.commit()

        if stage == "claimed_final_context":
            calls = 0
            original = execution.context

            def retract(scope):  # type: ignore[no-untyped-def]
                nonlocal calls
                calls += 1
                result = original(scope)
                if calls == 3:
                    erase()
                return result

            changed = replace(execution, context=retract)
            with pytest.raises(HTTPException, match="provenance retracted"):
                optimization.execute_claim(db, claim, actor, changed, lambda: NOW)
            assert calls == 3 and not server.writes
            db.rollback()
        else:
            erase()
            optimization.reconcile_attempt(
                db, wid, claim.attempt_id, execution, lambda: NOW + timedelta(seconds=1)
            )
            assert db.get(GoogleOriginalCompletion, claim.attempt_id) is not None
            assert len(server.writes) == 1
        db.expire_all()
        assert db.get(V3Assessment, numeric_id) is None
        assert not list(db.scalars(select(CandidateJob).where(CandidateJob.workspace_id == wid)))
        link = db.get(CandidateReviewLink, review.review_id)
        assert link and link.candidate_result_id is None and link.candidate_workspace_id is None
        assert db.get(ProviderExecutionReview, review.review_id) is not None
        assert [
            (r.id, r.state, r.amount_micros)
            for r in db.scalars(select(ProviderExposureReservation))
        ] == holds
        assert (
            db.scalar(
                select(ProviderExecutionReceipt.id).where(
                    ProviderExecutionReceipt.attempt_id == claim.attempt_id
                )
            )
            is not None
        )
