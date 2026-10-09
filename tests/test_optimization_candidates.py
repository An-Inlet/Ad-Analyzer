"""Non-emitting queue uses real owned source/session state and mocked native reads."""

from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from app.commerce.models import CommerceMeasurementPublication, CommerceStore
from app.commerce.sync import CommerceSyncService
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerSession, CustomerUser
from app.goals import service as goals
from app.lifecycle.privacy import bump_workspace_export_revision
from app.optimization_candidates import service as s
from app.optimization_candidates.compiler import compile_candidate
from app.optimization_candidates.contracts import (
    CandidateEvidence,
    CandidateObservation,
    CandidatePolicy,
    CandidateScope,
    CandidateWork,
    SourceFence,
)
from app.optimization_candidates.models import CandidateJob, CandidateResult
from app.publication import execution_mandates as mandates
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import ProviderMandatePolicy
from app.publication.execution_models import ProviderExecutionAttempt, ProviderExposureReservation
from app.publication.optimization_contracts import GoogleBudgetSetV1
from app.settings import Settings
from app.shopify.models import ShopifyConnection
from app.workspaces.models import Workspace
from fastapi import HTTPException
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from tests.candidate_current_fixture import current_candidate_read as current_candidate_read
from tests.test_commerce_measurement import NOW, FakeMeasurement, source
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_durable_optimization import ready
from tests.test_execution_session_authorizer import guard, revoke
from tests.test_shopify_sales import configuration as configuration


def fixture(
    db: Session,
    config: Settings,
    path: Path,
    with_receipt: bool = False,
    provider: str = "google_ads",
) -> tuple[
    CustomerPrincipal,
    CandidateWork,
    CandidateObservation,
    ProviderMandatePolicy,
    s.CandidateRuntime,
    Any,
]:
    if db.get_bind().dialect.name == "sqlite":
        db.execute(text("PRAGMA foreign_keys=ON"))
    wid, actor, binding, account, target, _, native, server = ready(db, config, path, provider)
    _, token = guard(db, actor)
    user, session = db.get(CustomerUser, actor), db.get(CustomerSession, token)
    assert user and session
    principal = CustomerPrincipal(user=user, session=session)
    identity = FakeProvider()
    identity.issuer = user.issuer
    shop = db.scalar(select(ShopifyConnection).where(ShopifyConnection.workspace_id == wid))
    assert shop
    store = db.get(CommerceStore, shop.commerce_store_id)
    assert store
    store.last_sync_at = None
    db.commit()
    CommerceSyncService(db, config, FakeMeasurement(config, [([source()], None)])).page(
        wid, now=NOW
    )
    publication = db.scalar(
        select(CommerceMeasurementPublication).where(
            CommerceMeasurementPublication.workspace_id == wid
        )
    )
    assert publication
    ledger, mandate = mandates.checked(db, wid, binding, actor, lambda: NOW)
    q = native.qualification_reader(db, binding, account, target, NOW)
    state = native.transport(account).read_current(
        account,
        target,
        q.money,
        q.qualification_id,
        q.qualification_revision,
        native.context(account),
        NOW,
    )
    goal = goals.owned(db, wid, mandate.goal_id)
    workspace = db.get(Workspace, wid)
    assert workspace
    scope = CandidateScope(
        account=account,
        mandate=binding,
        goal_id=goal.id,
        goal_revision=goal.revision,
        goal_digest=fingerprint(
            "inlet.optimization-goal.v1", {"definition": goals.current(db, goal).definition}
        ),
        target=target,
        budget_owner_key=state.budget_owner.key(account),
        target_set_digest=state.budget_owner.target_set_digest(),
        source=SourceFence(
            workspace_privacy_revision=workspace.export_privacy_revision,
            store_id=store.id,
            publication_id=publication.id,
            generation=publication.generation,
            privacy_epoch=publication.privacy_epoch,
            publication_revision=publication.publication_revision,
            source_revision=publication.source_revision,
            manifest_digest=publication.manifest_digest,
        ),
    )
    if with_receipt:
        from app.commerce.evidence import digest
        from app.publication import optimization as o
        from app.publication.coordinator import read_owned_outcome_receipt
        from app.publication.optimization_contracts import GoogleBudgetSetV1

        review = o.prepare_optimization(
            db,
            wid,
            binding,
            account,
            target,
            GoogleBudgetSetV1(amount_micros=45_000_000),
            "a" * 64,
            actor,
            native,
            lambda: NOW,
        )
        o.approve_optimization(
            db, wid, review.id, review.digest, review.plan_digest, actor, native, lambda: NOW
        )
        run = o.create_run(db, wid, review.id, actor, native, lambda: NOW)
        claim = o.claim_step(db, wid, run.id, actor, native, lambda: NOW)
        assert claim
        o.execute_claim(db, claim, actor, native, lambda: NOW)
        receipt = read_owned_outcome_receipt(db, wid, claim.attempt_id, actor)
        assert receipt
        scope = scope.model_copy(
            update={
                "source": scope.source.model_copy(
                    update={
                        "attempt_id": claim.attempt_id,
                        "receipt_id": receipt.receipt_id,
                        "receipt_sequence": receipt.sequence,
                        "receipt_digest": receipt.receipt_digest,
                        "projection_digest": digest(
                            ["inlet.owned-receipt.v1", receipt.model_dump(mode="json")]
                        ),
                    }
                )
            }
        )
    policy = CandidatePolicy(
        workspace_id=wid,
        environment="contract_test",
        policy_id="a" * 32,
        revision=1,
        budget_step_micros=1_000_000,
        minimum_observations=10,
    )
    work = CandidateWork(scope=scope, policy=policy)
    evidence = CandidateEvidence(
        scope_digest=scope.digest(),
        source_schema="test.controlled.v1",
        source_digest="b" * 64,
        source_reference=publication.id,
        qualification="contract_scenario",
        direction="increase",
        observation_count=20,
        observed_at=NOW,
        expires_at=NOW + timedelta(minutes=2),
    )
    observation = CandidateObservation(scope=scope, state=state, evidence=evidence)
    runtime = s.CandidateRuntime(
        environment="contract_test",
        identity=identity,
        reader=lambda db, scope, now: observation,
        policy_reader=lambda db, wid, pid, rev: policy,
        clock=lambda: NOW,
    )
    db.commit()
    return principal, work, observation, mandate, runtime, server


@pytest.mark.planning_boundary
def test_durable_read_dedup_no_execution_and_privacy_erasure(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    current_candidate_read: tuple[Engine, Any],
) -> None:
    from tests.candidate_read_retained_fixture import load_candidate_read_fixture

    customer_engine, ids = current_candidate_read
    with Session(customer_engine) as db:
        principal, work, _, _, runtime, server = load_candidate_read_fixture(db, ids)
        row = s.enqueue(db, principal, work, runtime)
        identifier, wid = row.id, row.workspace_id
        assert s.enqueue(db, principal, work, runtime).id == identifier
        db.commit()
    assert s.run_candidate_reads(customer_engine, lambda: runtime) == {"completed": 1}
    assert s.run_candidate_reads(customer_engine, lambda: runtime) == {}
    with Session(customer_engine) as db:
        result = db.scalar(select(CandidateResult))
        assert result
        decision = s.read_result(
            db, wid, result.id, s.principal_for(db, s.load(db, wid, result.job_id)), runtime
        )
        assert decision.status == "suggested" and isinstance(decision.action, GoogleBudgetSetV1)
        assert decision.action.amount_micros == 51_000_000
        assert decision.spending_authority == "none" and not decision.dispatch_ready
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
        assert db.scalar(select(func.count()).select_from(ProviderExposureReservation)) == 0
        bump_workspace_export_revision(db, wid)
        db.commit()
        assert db.scalar(select(func.count()).select_from(CandidateJob)) == 0
        assert db.scalar(select(func.count()).select_from(CandidateResult)) == 0


@pytest.mark.planning_boundary
def test_unqualified_default_and_cumulative_limit(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    current_candidate_read: tuple[Engine, Any],
) -> None:
    from tests.candidate_read_retained_fixture import load_candidate_read_fixture

    customer_engine, ids = current_candidate_read
    with Session(customer_engine) as db:
        _, work, observation, mandate, _, _ = load_candidate_read_fixture(db, ids)
        unqualified = observation.model_copy(
            update={
                "evidence": observation.evidence.model_copy(
                    update={
                        "qualification": "unqualified",
                        "direction": "none",
                        "observation_count": None,
                    }
                )
            }
        )
        result = compile_candidate(unqualified, work.policy, mandate, 0, 0, NOW)
        assert result.status == "blocked" and result.action is None
        unset = work.policy.model_copy(update={"budget_step_micros": None})
        assert (
            "numeric_policy_unconfigured"
            in compile_candidate(observation, unset, mandate, 0, 0, NOW).reasons
        )
        exhausted = compile_candidate(
            observation, work.policy, mandate, mandate.positive_change_cap_micros, 0, NOW
        )
        assert exhausted.action is None
        final = compile_candidate(
            observation, work.policy, mandate, mandate.positive_change_cap_micros - 10_000, 0, NOW
        )
        assert (
            isinstance(final.action, GoogleBudgetSetV1) and final.action.amount_micros == 50_010_000
        )


@pytest.mark.parametrize("phase", ["before", "during"])
@pytest.mark.planning_boundary
def test_revocation_blocks_saved_suggestion(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    phase: str,
    current_candidate_read: tuple[Engine, Any],
) -> None:
    from tests.candidate_read_retained_fixture import load_candidate_read_fixture

    customer_engine, ids = current_candidate_read
    with Session(customer_engine) as db:
        principal, work, observation, _, runtime, _ = load_candidate_read_fixture(db, ids)
        row = s.enqueue(db, principal, work, runtime)
        wid, identifier, token = row.workspace_id, row.id, principal.session.digest
    if phase == "before":
        revoke(customer_engine, token)
    else:

        def read(db, scope, now):  # type: ignore[no-untyped-def]
            revoke(customer_engine, token)
            return observation

        runtime = replace(runtime, reader=read)
    assert s.process(customer_engine, wid, identifier, runtime) == "blocked"
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(CandidateResult)) == 0


@pytest.mark.planning_boundary
def test_expiry_backoff_and_default_inert(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    current_candidate_read: tuple[Engine, Any],
) -> None:
    from tests.candidate_read_retained_fixture import load_candidate_read_fixture

    customer_engine, ids = current_candidate_read
    assert s.run_candidate_reads(None) == {}  # type: ignore[arg-type]
    with Session(customer_engine) as db:
        principal, work, _, _, runtime, _ = load_candidate_read_fixture(db, ids)
        row = s.enqueue(db, principal, work, runtime)
        wid, identifier = row.workspace_id, row.id

    def broken(db, scope, now):  # type: ignore[no-untyped-def]
        raise RuntimeError("never store raw secret exception")

    broken_runtime = replace(runtime, reader=broken)
    assert s.process(customer_engine, wid, identifier, broken_runtime) == "retry"
    assert s.run_candidate_reads(customer_engine, lambda: broken_runtime) == {}
    with Session(customer_engine) as db:
        pending = db.get(CandidateJob, identifier)
        assert (
            pending
            and pending.attempts == 1
            and pending.error_code == "candidate_source_unavailable"
        )
        pending.due_at = NOW
        db.commit()
    assert s.process(customer_engine, wid, identifier, runtime) == "completed"
    with Session(customer_engine) as db:
        result = db.scalar(select(CandidateResult))
        assert result
        with pytest.raises(HTTPException):
            s.read_result(
                db,
                wid,
                result.id,
                s.principal_for(db, s.load(db, wid, result.job_id)),
                replace(runtime, clock=lambda: NOW + timedelta(minutes=3)),
            )


@pytest.mark.parametrize(
    "change", ["correction", "privacy", "publication", "foreign", "generation"]
)
@pytest.mark.planning_boundary
def test_source_change_during_read_cannot_publish(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    change: str,
    current_candidate_read: tuple[Engine, Any],
) -> None:
    from tests.candidate_read_retained_fixture import load_candidate_read_fixture

    customer_engine, ids = current_candidate_read
    from app.commerce.evidence import publish
    from app.commerce.ledger import revise_days
    from app.commerce.models import CommerceEvidenceState

    with Session(customer_engine) as db:
        principal, work, observation, _, runtime, _ = load_candidate_read_fixture(db, ids)
        row = s.enqueue(db, principal, work, runtime)
        wid, identifier = row.workspace_id, row.id

    def changed(db, scope, now):  # type: ignore[no-untyped-def]
        if change == "foreign":
            return observation.model_copy(
                update={
                    "scope": scope.model_copy(
                        update={
                            "account": scope.account.model_copy(update={"workspace_id": wid + 100})
                        }
                    )
                }
            )
        if change == "privacy":
            bump_workspace_export_revision(db, wid)
        elif change == "generation":
            state = db.get(CommerceEvidenceState, scope.source.store_id)
            assert state
            state.generation += 1
        else:
            store = db.get(CommerceStore, scope.source.store_id)
            assert store
            if change == "correction":
                revise_days(db, store, {NOW.date()}, NOW)
            else:
                publish(
                    db, store, NOW - timedelta(days=30), NOW, NOW + timedelta(seconds=1), "2026-07"
                )
        db.commit()
        return observation

    result = s.process(customer_engine, wid, identifier, replace(runtime, reader=changed))
    assert result in {"blocked", "retry"}
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(CandidateResult)) == 0
        if change in {"privacy", "correction", "publication"}:
            assert db.get(CandidateJob, identifier) is None


@pytest.mark.planning_boundary
def test_strict_export_and_foreign_read(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    current_candidate_read: tuple[Engine, Any],
) -> None:
    from tests.candidate_read_retained_fixture import load_candidate_read_fixture

    customer_engine, ids = current_candidate_read
    from app.database.session import Base
    from app.lifecycle.export_serializers import serialize
    from app.lifecycle.local_work import verify_work_registry

    with Session(customer_engine) as db:
        principal, work, _, _, runtime, _ = load_candidate_read_fixture(db, ids)
        row = s.enqueue(db, principal, work, runtime)
        wid, identifier = row.workspace_id, row.id
    assert s.process(customer_engine, wid, identifier, runtime) == "completed"
    verify_work_registry()
    with Session(customer_engine) as db:
        for name in ["optimization_candidate_jobs", "optimization_candidate_results"]:
            mapping = db.execute(select(Base.metadata.tables[name])).mappings().one()
            export, missing = serialize(name, dict(mapping))
            assert not missing
            assert "auth_session_digest" not in export and "fence" not in export
            assert "dispatch_ready" in str(export) or "prepare_suggestion_only" in str(export)
        result = db.scalar(select(CandidateResult))
        assert result
        principal = s.principal_for(db, s.load(db, wid, identifier))
        with pytest.raises(HTTPException):
            s.read_result(db, wid + 10, result.id, principal, runtime)


@pytest.mark.planning_boundary
def test_claim_fence_not_clobbered_and_lease_reclaims_only_reads(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    current_candidate_read: tuple[Engine, Any],
) -> None:
    from tests.candidate_read_retained_fixture import load_candidate_read_fixture

    customer_engine, ids = current_candidate_read
    with Session(customer_engine) as db:
        principal, work, _, _, runtime, _ = load_candidate_read_fixture(db, ids)
        row = s.enqueue(db, principal, work, runtime)
        wid, identifier = row.workspace_id, row.id
        first = s.claim(db, wid, identifier, runtime)
        assert first
        assert s.claim(db, wid, identifier, runtime) is None
        s.retire_or_retry(db, wid, identifier, None, NOW, retry=False)
        assert s.load(db, wid, identifier).fence == first
        db.commit()
        later = replace(runtime, clock=lambda: NOW + timedelta(minutes=3))
        second = s.claim(db, wid, identifier, later)
        assert second and second != first
        s.retire_or_retry(db, wid, identifier, first, NOW, retry=True)
        assert s.load(db, wid, identifier).fence == second


def test_receipt_append_erases_derived_only(
    customer_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    from app.publication import optimization as o

    with Session(customer_engine) as db:
        principal, work, _, _, runtime, _ = fixture(db, configuration, tmp_path, True)
        row = s.enqueue(db, principal, work, runtime)
        wid, identifier = row.workspace_id, row.id
    assert s.process(customer_engine, wid, identifier, runtime) == "completed"
    with Session(customer_engine) as db:
        attempt_id = work.scope.source.attempt_id
        assert attempt_id
        _, _, _, request = o.evidence_lock(db, wid, attempt_id)
        at = NOW + timedelta(seconds=1)
        o.record_receipt(db, wid, attempt_id, o.unknown(request, lambda: at), lambda: at)
        db.commit()
        assert db.scalar(select(func.count()).select_from(CandidateJob)) == 0
        assert db.scalar(select(func.count()).select_from(CandidateResult)) == 0
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 1
        reservation = db.scalar(select(ProviderExposureReservation))
        assert reservation and reservation.state == "held"


@pytest.mark.planning_boundary
def test_closure_erases_candidates_transactionally(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    current_candidate_read: tuple[Engine, Any],
) -> None:
    from tests.candidate_read_retained_fixture import load_candidate_read_fixture

    customer_engine, ids = current_candidate_read
    from app.lifecycle.quiescing import quiesce

    from tests.test_customer_quiescing import confirmed

    with Session(customer_engine) as db:
        principal, work, _, _, runtime, _ = load_candidate_read_fixture(db, ids)
        row = s.enqueue(db, principal, work, runtime)
        wid, identifier = row.workspace_id, row.id
        principal.user.issuer = FakeProvider().issuer
        runtime = replace(runtime, identity=FakeProvider())
        db.commit()
        request, digest = confirmed(db, principal, wid, NOW)
        quiesce(db, principal, runtime.identity, wid, request, 1, digest, NOW)
        db.rollback()
        assert db.get(CandidateJob, identifier)
        quiesce(db, principal, runtime.identity, wid, request, 1, digest, NOW)
        db.commit()
        assert db.get(CandidateJob, identifier) is None


@pytest.mark.parametrize("provider", ["google_ads", "meta_ads", "tiktok_ads"])
@pytest.mark.planning_boundary
def test_all_provider_read_queue_is_non_emitting(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    provider: str,
    current_candidate_read: tuple[Engine, Any],
) -> None:
    from tests.candidate_read_retained_fixture import load_candidate_read_fixture

    customer_engine, ids = current_candidate_read
    with Session(customer_engine) as db:
        principal, work, _, _, runtime, server = load_candidate_read_fixture(db, ids)
        row = s.enqueue(db, principal, work, runtime)
        wid, identifier = row.workspace_id, row.id
    assert s.process(customer_engine, wid, identifier, runtime) == "completed"
    assert len(server.writes if provider == "google_ads" else server.posts) == 0
    with Session(customer_engine) as db:
        result = db.scalar(select(CandidateResult))
        assert result and result.decision["status"] == "suggested"
        assert result.decision["spending_authority"] == "none"


@pytest.mark.planning_boundary
def test_actual_association_cannot_register_as_measured_learning(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    current_candidate_read: tuple[Engine, Any],
) -> None:
    from tests.candidate_read_retained_fixture import load_candidate_read_fixture

    customer_engine, ids = current_candidate_read
    with Session(customer_engine) as db:
        principal, work, observation, _, runtime, _ = load_candidate_read_fixture(db, ids)
        row = s.enqueue(db, principal, work, runtime)
        wid, identifier = row.workspace_id, row.id
    evidence = observation.evidence.model_copy(
        update={
            "qualification": "qualified_learning",
            "source_schema": "inlet.owned-outcome-assessment.v3",
            "qualification_profile": "association",
            "qualification_revision": 1,
            "qualification_digest": "f" * 64,
        }
    )
    runtime = replace(
        runtime,
        reader=lambda db, scope, now: observation.model_copy(update={"evidence": evidence}),
        learning_profiles=frozenset({(evidence.source_schema, "association", 1, "f" * 64)}),
    )
    assert s.process(customer_engine, wid, identifier, runtime) == "blocked"
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(CandidateResult)) == 0


def test_failed_tenant_does_not_starve_other_owned_read(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests import test_google_action_plans as fixtures
    from tests.test_mandates import seed

    monkeypatch.setattr(
        fixtures, "seed", lambda db, config, **kwargs: seed(db, config, "first", **kwargs)
    )
    with Session(customer_engine) as db:
        first, work1, observation1, _, runtime1, _ = fixture(db, configuration, tmp_path / "first")
        first_id = s.enqueue(db, first, work1, runtime1).id
    monkeypatch.setattr(
        fixtures, "seed", lambda db, config, **kwargs: seed(db, config, "second", **kwargs)
    )
    with Session(customer_engine) as db:
        second, work2, observation2, _, runtime2, _ = fixture(
            db, configuration, tmp_path / "second"
        )
        s.enqueue(db, second, work2, runtime2)

    def reader(db, scope, now):  # type: ignore[no-untyped-def]
        if scope.account.workspace_id == work1.scope.account.workspace_id:
            raise RuntimeError("tenant source unavailable")
        return observation2

    policies = {work1.policy.workspace_id: work1.policy, work2.policy.workspace_id: work2.policy}
    runtime = replace(
        runtime1, reader=reader, policy_reader=lambda db, wid, pid, rev: policies[wid]
    )
    assert s.run_candidate_reads(customer_engine, lambda: runtime) == {"retry": 1, "completed": 1}
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(CandidateResult)) == 1
        first_job = db.get(CandidateJob, first_id)
        assert first_job and first_job.state == "pending"
