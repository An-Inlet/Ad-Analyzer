"""Actual owned consumer with explicitly synthetic qualification/effect/calibration.

No real source is promoted: default registries and producers remain absent.
"""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest
from app.commerce.models import CommerceMeasurementPublication
from app.directional_feedback.contracts import (
    DirectionalAssociationPolicyV1,
    DirectionalQualificationV1,
    QualifiedDirectionalFactsV1,
)
from app.directional_feedback.evaluator import evaluate_directional_association
from app.directional_feedback.reader import (
    DirectionalReadRuntime,
    directional_policy_for,
    directional_qualification_for,
    get_directional_runtime,
    read_directional_inputs,
    resolve_original_opportunity,
)
from app.outcome_feedback.models import ContributionSlot
from app.outcome_feedback.snapshot import apply_owned_feedback, read_feedback_snapshot
from app.settings import Settings
from app.workspaces.models import Workspace
from fastapi import HTTPException
from sqlalchemy import Engine, delete
from sqlalchemy.orm import Session

from tests import test_feedback_snapshot as fixtures
from tests.feedback_snapshot_retained_fixture import (
    snapshot_receipt_source as snapshot_receipt_source,
)
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_feedback_policy import policy as feedback_policy
from tests.test_shopify_sales import configuration as configuration


def assembly(
    db: Session, configuration: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Any:
    captured = []
    original = cast(Any, fixtures).fixture

    def capture(*args: Any, **kwargs: Any) -> Any:
        result = original(*args, **kwargs)
        captured.append(result)
        return result

    with monkeypatch.context() as scoped:
        scoped.setattr(fixtures, "fixture", capture)
        wid, actor, saved, value, authorize, later, mature, principal = fixtures.prepare(
            db, configuration, tmp_path, scoped
        )
        # Preserve only the explicit synthetic receipt seam beyond the helper context.
        from app.outcome_feedback import service

        synthetic = cast(Any, service)._snapshot
    monkeypatch.setattr(service, "_snapshot", synthetic)
    _, work, _, _, candidate, _ = captured[0]
    feedback = feedback_policy(value)
    scope, slot = apply_owned_feedback(
        db,
        wid,
        actor,
        saved,
        feedback.family,
        None,
        authorize,
        lambda: later,
        decisions=lambda _: feedback,
        policies=lambda _: mature,
    )
    assert slot
    snapshot = read_feedback_snapshot(
        db,
        wid,
        actor,
        saved,
        feedback.family,
        authorize,
        lambda: later,
        decisions=lambda _: feedback,
        policies=lambda _: mature,
    )
    pub = db.get(CommerceMeasurementPublication, value.publication_id)
    workspace = db.get(Workspace, wid, populate_existing=True)
    assert pub and workspace
    source = work.scope.source.model_copy(
        update={
            "publication_id": pub.id,
            "publication_revision": pub.publication_revision,
            "source_revision": pub.source_revision,
            "manifest_digest": pub.manifest_digest,
            "workspace_privacy_revision": workspace.export_privacy_revision,
        }
    )
    work = work.model_copy(update={"scope": work.scope.model_copy(update={"source": source})})
    candidate = replace(candidate, clock=lambda: later)
    from app.directional_feedback.reader import budget_change

    change = budget_change(db, wid, value.receipt.run_id)
    assert change in {"increase", "decrease"}
    policy = DirectionalAssociationPolicyV1(
        policy_id="1" * 32,
        family="2" * 32,
        revision=1,
        environment="contract_test",
        feedback_policy_digest=feedback.policy_digest,
        candidate_policy_digest=work.policy.digest(),
        feedback_family=feedback.family,
        scope_digest=scope.scope_digest,
        calibration_digest="3" * 64,
        qualification_profile="4" * 32,
        negative_cutoff=Decimal("-0.1"),
        positive_cutoff=Decimal("0.1"),
        original_change=change,
        below_direction="decrease",
        above_direction="increase",
        minimum_contributions=1,
        minimum_qualified_completions=2,
        maximum_assessment_age_seconds=3600,
        maximum_facts_age_seconds=600,
        decision_lifetime_seconds=60,
    )
    qualification = DirectionalQualificationV1(
        profile_id=policy.qualification_profile,
        revision=1,
        environment="contract_test",
        policy_digest=policy.policy_digest,
        calibration_digest=policy.calibration_digest,
        scope_digest=scope.scope_digest,
        producer_family="5" * 32,
        evidence_mode="contract_scenario",
        starts_at=later - timedelta(seconds=1),
        ends_at=later + timedelta(hours=1),
    )

    def facts(
        session: Session, current: Any, completions: tuple[str, ...]
    ) -> QualifiedDirectionalFactsV1:
        return QualifiedDirectionalFactsV1(
            environment="contract_test",
            snapshot_digest=current.snapshot_digest,
            producer_family=qualification.producer_family,
            evidence_mode="contract_scenario",
            completion_digests=completions,
            assurance="independent_full_window",
            correction_state="settled_as_of",
            delivery_time="authoritative_interval",
            fresh_through=later,
            valid_until=later + timedelta(minutes=5),
        )

    runtime = DirectionalReadRuntime(
        candidate=candidate,
        policies=lambda _: policy,
        qualifications=lambda _: qualification,
        facts=facts,
        feedback_policies=lambda _: feedback,
        maturity_policies=lambda _: mature,
    )
    db.commit()
    return principal, work, saved, policy, qualification, runtime, later, slot.id, snapshot


@pytest.mark.planning_boundary
def test_real_owned_reader_and_explicit_mapping_keep_counts_separate(
    snapshot_receipt_source: Engine,
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    customer_engine = snapshot_receipt_source
    with Session(customer_engine) as db:
        principal, work, saved, policy, qualification, runtime, now, _, _ = assembly(
            db, configuration, tmp_path, monkeypatch
        )
        assert get_directional_runtime() is None and directional_policy_for(policy.family) is None
        assert directional_qualification_for(policy) is None
        inputs = read_directional_inputs(db, principal, work, saved, policy, runtime)
        assert (
            len(inputs.snapshot.contributions) == 1
            and inputs.facts
            and len(inputs.facts.completion_digests) == 2
        )
        result = evaluate_directional_association(inputs, policy, qualification, now)
        assert result.status == "recommended" and result.direction == "increase"
        assert result.qualified_completion_count == 2 and result.spending_authority == "none"
        assert evaluate_directional_association(inputs, None, None, now).status == "blocked"
        missing = read_directional_inputs(
            db, principal, work, saved, policy, replace(runtime, facts=None)
        )
        assert (
            evaluate_directional_association(missing, policy, qualification, now).status
            == "blocked"
        )
        assert (
            resolve_original_opportunity(db, principal, work, runtime.candidate)
            == inputs.opportunity
        )


@pytest.mark.planning_boundary
def test_required_qualification_cohort_freshness_and_policy_fail_closed(
    snapshot_receipt_source: Engine,
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    customer_engine = snapshot_receipt_source
    with Session(customer_engine) as db:
        principal, work, saved, policy, qualification, runtime, now, _, _ = assembly(
            db, configuration, tmp_path, monkeypatch
        )
        inputs = read_directional_inputs(db, principal, work, saved, policy, runtime)
        assert inputs.facts
        for modified in (
            inputs.model_copy(update={"facts": None}),
            inputs.model_copy(update={"original_changes": ("unsupported",)}),
            inputs.model_copy(
                update={"facts": inputs.facts.model_copy(update={"correction_state": "unresolved"})}
            ),
            inputs.model_copy(
                update={"facts": inputs.facts.model_copy(update={"delivery_time": "unavailable"})}
            ),
            inputs.model_copy(
                update={"facts": inputs.facts.model_copy(update={"snapshot_digest": "0" * 64})}
            ),
        ):
            blocked = evaluate_directional_association(modified, policy, qualification, now)
            assert (
                blocked.status == "blocked"
                and blocked.direction == "none"
                and blocked.expires_at is None
            )
        assert (
            evaluate_directional_association(
                inputs, policy, qualification, now + timedelta(hours=2)
            ).status
            == "blocked"
        )
        with pytest.raises(HTTPException, match="registered directional policy"):
            read_directional_inputs(
                db, principal, work, saved, policy, replace(runtime, policies=lambda _: None)
            )
        other = policy.model_copy(update={"positive_cutoff": Decimal("0.3")})
        profile = qualification.model_copy(update={"policy_digest": other.policy_digest})
        assert evaluate_directional_association(inputs, other, profile, now).status == "no_change"
        live_snapshot = inputs.snapshot.model_copy(
            update={"scope": inputs.snapshot.scope.model_copy(update={"environment": "live"})}
        )
        live_policy = policy.model_copy(
            update={"environment": "live", "scope_digest": live_snapshot.scope.scope_digest}
        )
        live_profile = qualification.model_copy(
            update={
                "environment": "live",
                "scope_digest": live_policy.scope_digest,
                "policy_digest": live_policy.policy_digest,
            }
        )
        live_inputs = inputs.model_copy(
            update={
                "snapshot": live_snapshot,
                "opportunity": inputs.opportunity.model_copy(update={"environment": "live"}),
                "facts": inputs.facts.model_copy(
                    update={"environment": "live", "snapshot_digest": live_snapshot.snapshot_digest}
                ),
            }
        )
        live_result = evaluate_directional_association(live_inputs, live_policy, live_profile, now)
        assert "contract_qualification_cannot_enable_live" in live_result.reasons
        assert "contract_facts_cannot_enable_live" in live_result.reasons
        strict = policy.model_copy(update={"minimum_qualified_completions": 3})
        strict_profile = qualification.model_copy(update={"policy_digest": strict.policy_digest})
        failed = evaluate_directional_association(inputs, strict, strict_profile, now)
        assert "insufficient_qualified_completions" in failed.reasons
        assert "insufficient_active_contributions" not in failed.reasons
        opposite = inputs.model_copy(
            update={
                "original_changes": (
                    "decrease" if policy.original_change == "increase" else "increase",
                )
            }
        )
        assert (
            "intervention_cohort_mismatch"
            in evaluate_directional_association(opposite, policy, qualification, now).reasons
        )
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            DirectionalAssociationPolicyV1.model_validate(
                policy.model_dump(exclude={"positive_cutoff"})
            )


@pytest.mark.planning_boundary
def test_retraction_and_missing_held_head_cannot_reuse_old_feedback(
    snapshot_receipt_source: Engine,
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    customer_engine = snapshot_receipt_source
    from app.publication.execution_models import ProviderExposureReservation

    with Session(customer_engine) as db:
        principal, work, saved, policy, qualification, runtime, now, slot_id, _ = assembly(
            db, configuration, tmp_path, monkeypatch
        )
        first = read_directional_inputs(db, principal, work, saved, policy, runtime)
        original_facts = runtime.facts

        def retract(session: Session, snap: Any, completions: tuple[str, ...]) -> Any:
            assert original_facts
            result = original_facts(session, snap, completions)
            session.execute(delete(ContributionSlot).where(ContributionSlot.id == slot_id))
            return result

        with pytest.raises(HTTPException):
            read_directional_inputs(
                db, principal, work, saved, policy, replace(runtime, facts=retract)
            )
        db.rollback()
        assert (
            resolve_original_opportunity(db, principal, work, runtime.candidate).semantic_digest
            == first.opportunity.semantic_digest
        )
        reservation = db.get(
            ProviderExposureReservation, db.query(ProviderExposureReservation.id).scalar()
        )
        assert reservation
        reservation.state = "settled"
        db.flush()
        with pytest.raises(HTTPException, match="current retained original"):
            resolve_original_opportunity(db, principal, work, runtime.candidate)


@pytest.mark.planning_boundary
def test_newer_held_original_without_receipt_blocks_old_qualified_anchor(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.candidate_receipt_fixture import load_receipt_candidate
    from tests.directional_held_retained_fixture import graph, staged_held_source

    with staged_held_source(customer_engine, tmp_path / "held-source") as source:
        with Session(source.engine) as db:
            principal, work, _, _, runtime, _ = load_receipt_candidate(db, source.original)
            initial = resolve_original_opportunity(db, principal, work, runtime)
            assert not db.new and not db.dirty and not db.deleted
            db.commit()
        assert graph(source.engine) == source.before
        claim = source.claim_successor()
        assert claim and claim.attempt_id != initial.original_attempt_id
        claimed = graph(source.engine)
        with Session(source.engine) as db:
            principal, loaded_work, _, _, runtime, server = load_receipt_candidate(
                db, source.original
            )
            assert loaded_work == work and not server.writes
            with pytest.raises(HTTPException, match="verified current original action"):
                resolve_original_opportunity(db, principal, work, runtime)
        assert graph(source.engine) == claimed
