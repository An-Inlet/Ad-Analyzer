"""Actual DB erasure graph, with explicitly synthetic numeric assessment rows."""

from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from app.commerce.evidence import digest
from app.commerce.models import CommerceMeasurementPublication
from app.commerce.sync import CommerceSyncService
from app.customers.models import CustomerMembership, CustomerSession
from app.optimization_candidates.models import CandidateJob, CandidateResult
from app.outcome_feedback.models import (
    ContributionSlot,
    FeedbackRecord,
    V3Assessment,
    V3EvidenceDependency,
)
from app.outcome_feedback.service import EvidenceReference, apply_feedback, persist_assessment
from app.outcomes.feedback import FeedbackDecisionPolicy, prepare_feedback
from app.outcomes.maturity import IndependentReconciliationEvidence
from app.outcomes.owned_v3 import OwnedSnapshot, OwnedV3Assessment, OwnedV3Request, assess_owned_v3
from app.publication.execution_models import ProviderExecutionReceipt, ProviderExposureReservation
from app.publication.service import owner
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from tests.feedback_erasure_retained_fixture import (
    feedback_erasure_sources as feedback_erasure_sources,
)
from tests.test_commerce_measurement import NOW, FakeMeasurement, source
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_feedback_policy import assessment as assessment
from tests.test_feedback_policy import policy
from tests.test_owned_outcomes import evidence
from tests.test_shopify_sales import configuration as configuration


def seed_graph(
    db: Session, value: OwnedV3Assessment, config: Settings
) -> tuple[str, str, str, str]:
    wid = value.context.scope.workspace_id
    actor = db.scalar(
        select(CustomerMembership.user_id).where(CustomerMembership.workspace_id == wid)
    )
    assert actor
    later = NOW + timedelta(hours=1)
    assert (
        CommerceSyncService(
            db, config, FakeMeasurement(config, [([source(updated=later)], None)])
        ).page(wid, now=later)["status"]
        == "complete"
    )
    publications = list(
        db.scalars(
            select(CommerceMeasurementPublication)
            .where(CommerceMeasurementPublication.workspace_id == wid)
            .order_by(CommerceMeasurementPublication.publication_revision)
        )
    )
    assert len(publications) == 2
    row = V3Assessment(
        id=uuid4().hex,
        workspace_id=wid,
        store_id=value.context.scope.store_id,
        environment="contract_test",
        attempt_id=value.receipt.attempt_id,
        receipt_id=value.receipt.receipt_id,
        receipt_sequence=value.receipt.sequence,
        generation=value.context.scope.generation,
        privacy_epoch=value.context.scope.privacy_epoch,
        input_digest=value.input_digest,
        document_digest=digest(value.model_dump(mode="json")),
        document=value.model_dump(mode="json"),
        created_at=NOW,
    )
    db.add(row)
    db.flush()
    for i, pub in enumerate(publications):
        db.add(
            V3EvidenceDependency(
                assessment_id=row.id,
                ordinal=i,
                workspace_id=wid,
                publication_id=pub.id,
                manifest_digest=pub.manifest_digest,
                completion_digest=pub.completion_digest,
            )
        )
    contribution = prepare_feedback(
        value,
        policy(value),
        environment="contract_test",
        expected_assessment_digest=row.document_digest,
    )
    feedback = FeedbackRecord(
        id=uuid4().hex,
        workspace_id=wid,
        environment="contract_test",
        attempt_id=row.attempt_id,
        assessment_id=row.id,
        assessment_digest=row.document_digest,
        policy_family="fixture",
        policy_digest=contribution.policy_digest,
        scope_digest="1" * 64,
        document_digest=digest(contribution.model_dump(mode="json")),
        document=contribution.model_dump(mode="json"),
        state="eligible",
        created_at=NOW,
    )
    db.add(feedback)
    db.flush()
    slot = ContributionSlot(
        id=uuid4().hex,
        workspace_id=wid,
        environment="contract_test",
        attempt_id=row.attempt_id,
        policy_family="fixture",
        scope_digest="1" * 64,
        feedback_id=feedback.id,
        revision=1,
    )
    db.add(slot)
    db.flush()
    token = digest(["fixture-session", wid])
    db.add(
        CustomerSession(
            digest=token,
            user_id=actor,
            csrf_digest="1" * 64,
            created_at=int(NOW.timestamp()),
            expires_at=int(NOW.timestamp()) + 3600,
            authenticated_at=int(NOW.timestamp()),
        )
    )
    db.flush()
    # Minimal FK-valid cache rows: test erasure independent of candidate compilation.
    job = CandidateJob(
        id=uuid4().hex,
        workspace_id=wid,
        environment="contract_test",
        publication_id=publications[1].id,
        attempt_id=None,
        actor_id=actor,
        auth_session_digest=token,
        input_digest="7" * 64,
        work={},
        state="completed",
        attempts=1,
        due_at=NOW,
        created_at=NOW,
    )
    db.add(job)
    db.flush()
    db.add(
        CandidateResult(
            id=uuid4().hex,
            workspace_id=wid,
            job_id=job.id,
            input_digest="7" * 64,
            policy_digest="7" * 64,
            evidence_digest="7" * 64,
            decision_digest="7" * 64,
            decision={},
            created_at=NOW,
        )
    )
    db.commit()
    return row.id, publications[0].id, job.id, slot.id


@pytest.mark.parametrize(
    "erasure",
    [
        "dependency",
        "historical_publication",
        "assessment",
        "feedback",
        "slot",
        "slot_update",
        "source",
        "workspace",
    ],
)
@pytest.mark.planning_boundary
def test_any_dependency_erases_numeric_parent_and_workspace_candidate_cache(
    customer_engine: Engine,
    configuration: Settings,
    feedback_erasure_sources: Any,
    erasure: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    customer_engine, assessment, second = feedback_erasure_sources
    with Session(customer_engine) as db:
        identifier, historical, job, slot = seed_graph(db, assessment, configuration)
        from app.optimization_candidates.service import enqueue, process

        from tests.candidate_read_retained_fixture import load_candidate_read_fixture

        principal, work, _, _, runtime, _ = load_candidate_read_fixture(db, second)
        other_job = enqueue(db, principal, work, runtime)
        other_id, other_wid = other_job.id, other_job.workspace_id
        assert process(customer_engine, other_wid, other_id, runtime) == "completed"
        from app.lifecycle.privacy import workspace_export_revision

        privacy_before = workspace_export_revision(db, assessment.context.scope.workspace_id)
        if erasure == "dependency":
            foreign_pub = db.scalar(
                select(CommerceMeasurementPublication).where(
                    CommerceMeasurementPublication.workspace_id == other_wid
                )
            )
            assert foreign_pub
            with pytest.raises(IntegrityError), db.begin_nested():
                db.add(
                    V3EvidenceDependency(
                        assessment_id=identifier,
                        ordinal=32,
                        workspace_id=other_wid,
                        publication_id=foreign_pub.id,
                        manifest_digest=foreign_pub.manifest_digest,
                        completion_digest=foreign_pub.completion_digest,
                    )
                )
                db.flush()
            current_slot = db.get(ContributionSlot, slot)
            assert current_slot
            with pytest.raises(IntegrityError), db.begin_nested():
                db.add(
                    ContributionSlot(
                        id=uuid4().hex,
                        workspace_id=current_slot.workspace_id,
                        environment="live",
                        attempt_id=current_slot.attempt_id,
                        policy_family=current_slot.policy_family,
                        scope_digest=current_slot.scope_digest,
                        feedback_id=current_slot.feedback_id,
                        revision=1,
                    )
                )
                db.flush()
            assert db.get(CandidateJob, job) is not None
        receipts = set(db.scalars(select(ProviderExecutionReceipt.id)))
        reservations = set(db.scalars(select(ProviderExposureReservation.id)))
        if erasure == "dependency":
            db.execute(
                delete(V3EvidenceDependency).where(
                    V3EvidenceDependency.assessment_id == identifier,
                    V3EvidenceDependency.ordinal == 0,
                )
            )
        elif erasure == "historical_publication":
            db.execute(
                delete(CommerceMeasurementPublication).where(
                    CommerceMeasurementPublication.id == historical
                )
            )
        elif erasure == "assessment":
            db.execute(delete(V3Assessment).where(V3Assessment.id == identifier))
        elif erasure == "feedback":
            db.execute(delete(FeedbackRecord).where(FeedbackRecord.assessment_id == identifier))
        elif erasure == "slot_update":
            current_slot = db.get(ContributionSlot, slot)
            assert current_slot
            current_slot.revision += 1
            db.flush()
        elif erasure == "source":
            from app.commerce.models import CommerceEvidenceState

            db.execute(
                delete(CommerceEvidenceState).where(
                    CommerceEvidenceState.store_id == assessment.context.scope.store_id
                )
            )
        elif erasure == "workspace":
            from app.commerce.evidence import lock_workspace
            from app.outcome_feedback.invalidation import erase_workspace_feedback

            lock_workspace(db, assessment.context.scope.workspace_id, active=True)
            erase_workspace_feedback(db, assessment.context.scope.workspace_id)
        else:
            db.execute(delete(ContributionSlot).where(ContributionSlot.id == slot))
        db.commit()
        db.expire_all()
        assert db.get(CandidateJob, job) is None
        assert workspace_export_revision(db, assessment.context.scope.workspace_id) > privacy_before
        assert db.get(CandidateJob, other_id) is not None
        assert db.scalar(select(func.count()).select_from(CandidateResult)) == 1
        if erasure == "slot_update":
            updated_slot = db.get(ContributionSlot, slot)
            assert updated_slot is not None and updated_slot.revision == 2
        else:
            assert db.get(ContributionSlot, slot) is None
        if erasure in {"dependency", "historical_publication", "assessment", "source", "workspace"}:
            assert db.get(V3Assessment, identifier) is None
            assert db.scalar(select(func.count()).select_from(V3EvidenceDependency)) == 0
            assert db.scalar(select(func.count()).select_from(FeedbackRecord)) == 0
        assert set(db.scalars(select(ProviderExecutionReceipt.id))) == receipts
        assert set(db.scalars(select(ProviderExposureReservation.id))) == reservations


def test_actual_insufficient_assessment_persists_idempotently_without_feedback(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
    with Session(customer_engine) as db:
        wid, actor, body, _, _ = evidence(db, configuration, tmp_path)
    request = OwnedV3Request.model_validate(body.model_dump(exclude={"policy_id"}))

    def authorize(db: Session) -> None:
        owner(db, wid, actor)

    value = assess_owned_v3(
        sessionmaker(customer_engine), wid, actor, request, authorize, lambda: NOW
    )
    with Session(customer_engine) as db:
        pub = db.get(CommerceMeasurementPublication, value.publication_id)
        assert pub
        refs = (
            EvidenceReference(
                publication_id=pub.id,
                manifest_digest=pub.manifest_digest,
                completion_digest=pub.completion_digest,
            ),
        )
        row = persist_assessment(db, wid, actor, value, refs, authorize, lambda: NOW)
        db.commit()
        assert persist_assessment(db, wid, actor, value, refs, authorize, lambda: NOW).id == row.id
        assert (
            apply_feedback(
                db, wid, actor, row.id, "uninstalled", "0" * 64, None, authorize, lambda: NOW
            )
            is None
        )
        assert db.scalar(select(func.count()).select_from(FeedbackRecord)) == 0


def test_explicit_fixture_policy_cas_replacement_and_retraction(
    customer_engine: Engine,
    configuration: Settings,
    assessment: OwnedV3Assessment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.outcome_feedback import service
    from app.outcome_feedback.service import SlotVersion, active_score
    from app.outcomes.owned_v3 import _snapshot, compare_owned_v3

    from tests.test_owned_outcomes_v3 import facts
    from tests.test_owned_outcomes_v3 import policy as maturity_policy

    wid = assessment.context.scope.workspace_id
    with Session(customer_engine) as db:
        actor = db.scalar(
            select(CustomerMembership.user_id).where(CustomerMembership.workspace_id == wid)
        )
        assert actor
        later = NOW + timedelta(hours=1)
        CommerceSyncService(
            db, configuration, FakeMeasurement(configuration, [([source(updated=later)], None)])
        ).page(wid, now=later)
        publications = list(
            db.scalars(
                select(CommerceMeasurementPublication)
                .where(CommerceMeasurementPublication.workspace_id == wid)
                .order_by(CommerceMeasurementPublication.publication_revision)
            )
        )
        request = OwnedV3Request(
            attempt_id=assessment.receipt.attempt_id,
            publication_id=publications[-1].id,
            before_start=assessment.before_window.start,
            before_end=assessment.before_window.end,
            after_start=assessment.after_window.start,
            after_end=assessment.after_window.end,
        )

        def authorize(db: Session) -> None:
            owner(db, wid, actor)

        original = _snapshot

        def synthetic_timing(*args: Any, **kwargs: Any) -> OwnedSnapshot:
            current = original(*args, **kwargs)
            # Sole synthetic timing seam; original DB owner/account/source fences still run.
            return current.model_copy(update={"receipt": assessment.receipt})

        monkeypatch.setattr(service, "_snapshot", synthetic_timing)
        snapshot = synthetic_timing(db, wid, actor, request, authorize, lambda: later)
        before = facts(snapshot.context, request.before_start, request.before_end, 10)
        after = facts(snapshot.context, request.after_start, request.after_end, 15)

        def bind(value: IndependentReconciliationEvidence) -> IndependentReconciliationEvidence:
            return value.model_copy(
                update={
                    "observations": tuple(
                        item.model_copy(
                            update={
                                "completion_digest": pub.completion_digest,
                                "observed_at": pub.published_at.replace(tzinfo=NOW.tzinfo),
                                "fresh_through": pub.source_window_end.replace(tzinfo=NOW.tzinfo),
                            }
                        )
                        for item, pub in zip(value.observations, publications, strict=True)
                    )
                }
            )

        maturity = maturity_policy(snapshot.context)
        value = compare_owned_v3(snapshot, request, maturity, bind(before), bind(after))
        refs = tuple(
            EvidenceReference(
                publication_id=pub.id,
                manifest_digest=pub.manifest_digest,
                completion_digest=pub.completion_digest,
            )
            for pub in publications
        )
        saved = persist_assessment(
            db, wid, actor, value, refs, authorize, lambda: later, policies=lambda _: maturity
        )
        db.commit()
        selected = policy(value)

        def apply(
            expected: SlotVersion | None, chosen: FeedbackDecisionPolicy | None
        ) -> ContributionSlot | None:
            return apply_feedback(
                db,
                wid,
                actor,
                saved.id,
                selected.family,
                "1" * 64,
                expected,
                authorize,
                lambda: later,
                policies=lambda _: maturity,
                decisions=lambda _: chosen,
            )

        assert apply(None, None) is None
        first = apply(None, selected)
        assert first and first.revision == 1
        db.commit()
        replay = apply(None, selected)
        assert replay is not None and replay.id == first.id
        newer = selected.model_copy(update={"version": 2})
        with pytest.raises(HTTPException) as error:
            apply(None, newer)
        assert error.value.status_code == 409
        active = db.get(FeedbackRecord, first.feedback_id)
        assert active
        expected = SlotVersion(
            slot_id=first.id, revision=first.revision, active_feedback_digest=active.document_digest
        )
        changed = apply(expected, newer)
        assert changed and changed.revision == 2
        db.commit()
        replay = apply(expected, newer)
        assert replay is not None and replay.revision == 2
        assert (
            active_score(
                db,
                wid,
                actor,
                "contract_test",
                selected.family,
                "1" * 64,
                authorize,
                lambda: later,
                policies=lambda _: maturity,
                decisions=lambda _: newer,
            )
            == selected.maximum_absolute_contribution
        )
        db.execute(
            delete(V3EvidenceDependency).where(
                V3EvidenceDependency.assessment_id == saved.id, V3EvidenceDependency.ordinal == 0
            )
        )
        db.commit()
        assert (
            active_score(
                db,
                wid,
                actor,
                "contract_test",
                selected.family,
                "1" * 64,
                authorize,
                lambda: later,
                policies=lambda _: maturity,
                decisions=lambda _: newer,
            )
            == 0
        )


def test_strict_feedback_exports_reject_foreign_and_future_documents(
    customer_engine: Engine,
    configuration: Settings,
    assessment: OwnedV3Assessment,
) -> None:
    from app.database.session import Base
    from app.lifecycle.export_serializers import serialize

    with Session(customer_engine) as db:
        seed_graph(db, assessment, configuration)
        for name in ("outcome_assessments_v3", "outcome_feedback_records"):
            mapping = dict(db.execute(select(Base.metadata.tables[name])).mappings().one())
            exported, missing = serialize(name, mapping)
            assert not missing and "document" in exported
            foreign = {**mapping, "workspace_id": 999}
            assert "document" in serialize(name, foreign)[1]
            future = {
                **mapping,
                "document": {**mapping["document"], "schema_version": "unsupported.v9"},
            }
            assert "document" in serialize(name, future)[1]


def test_actual_closure_erases_feedback_transactionally_and_keeps_finances(
    customer_engine: Engine,
    configuration: Settings,
    assessment: OwnedV3Assessment,
) -> None:
    from app.customers.access import CustomerPrincipal
    from app.customers.models import CustomerUser
    from app.lifecycle.quiescing import quiesce

    from tests.test_customer_identity import FakeProvider
    from tests.test_customer_quiescing import confirmed
    from tests.test_execution_session_authorizer import guard

    with Session(customer_engine) as db:
        identifier, _, job, slot = seed_graph(db, assessment, configuration)
        wid = assessment.context.scope.workspace_id
        actor = db.scalar(
            select(CustomerMembership.user_id).where(CustomerMembership.workspace_id == wid)
        )
        assert actor
        _, token = guard(db, actor)
        user, session = db.get(CustomerUser, actor), db.get(CustomerSession, token)
        assert user and session
        user.issuer = FakeProvider().issuer
        db.commit()
        principal = CustomerPrincipal(user=user, session=session)
        request, preview = confirmed(db, principal, wid, NOW)
        receipts = set(db.scalars(select(ProviderExecutionReceipt.id)))
        reservations = set(db.scalars(select(ProviderExposureReservation.id)))
        quiesce(db, principal, FakeProvider(), wid, request, 1, preview, NOW)
        db.rollback()
        assert (
            db.get(V3Assessment, identifier) is not None and db.get(CandidateJob, job) is not None
        )
        quiesce(db, principal, FakeProvider(), wid, request, 1, preview, NOW)
        db.commit()
        assert db.get(V3Assessment, identifier) is None and db.get(ContributionSlot, slot) is None
        assert db.get(CandidateJob, job) is None
        assert set(db.scalars(select(ProviderExecutionReceipt.id))) == receipts
        assert set(db.scalars(select(ProviderExposureReservation.id))) == reservations
