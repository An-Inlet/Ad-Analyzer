"""Actual Meta HTTP/native preview through explicit offline financial qualification."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerSession, CustomerUser
from app.initial_planning.contracts import InitialPreviewV1
from app.initial_planning.models import PreviewRow
from app.initial_planning.review_bridge import prepare_preview_review
from app.initial_planning.review_contracts import InitialPreviewReviewRuntime
from app.initial_planning.review_models import InitialPreviewReviewLink
from app.publication import customer_optimization, optimization
from app.publication.execution_contracts import ExposureEvidence
from app.publication.execution_models import ProviderExecutionReview, ProviderExposureReservation
from app.publication.optimization_execution_contracts import OptimizationQualification
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, delete, func, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from tests.initial_preview_review_fixture import ready_preview_review
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration


def ready(engine: Engine, config: Settings, monkeypatch: pytest.MonkeyPatch, replicas: Any) -> Any:
    planning, raw, server, actor, token, wid = ready_preview_review(
        engine, config, monkeypatch, replicas
    )
    planning = replace(planning, clock=lambda: datetime.now(UTC))
    document = InitialPreviewV1.model_validate(raw)
    _, _, provider = replicas
    assert planning.native is not None
    calls = []

    def qualify(db, binding, scope, target, now):  # type: ignore[no-untyped-def]
        calls.append("qualification")
        money = planning.native.catalog.inventory[0].money
        return OptimizationQualification(
            environment="contract_test",
            scope=scope,
            target=target,
            money=money,
            qualification_id="e" * 32,
            qualification_revision=1,
            profile="controlled_contract_profile",
            allowed_operations=["meta_budget_set_v1"],
            observed_at=now,
            expires_at=now + timedelta(minutes=2),
            evidence_digest="f" * 64,
            unresolved=[],
        )

    def exposure(db, intent, state, qualification, now):  # type: ignore[no-untyped-def]
        calls.append("exposure")
        held = int(
            db.scalar(
                select(func.coalesce(func.sum(ProviderExposureReservation.amount_micros), 0)).where(
                    ProviderExposureReservation.workspace_id == wid,
                    ProviderExposureReservation.state == "held",
                )
            )
            or 0
        )
        return ExposureEvidence(
            environment="contract_test",
            mandate=intent.mandate,
            account=intent.scope,
            covered_account_ids=[intent.scope.account.account_id],
            budget_owner_key=intent.budget_owner.key(intent.scope),
            target_set_digest=intent.approved_target_set_digest,
            state_digest=state.digest(),
            currency="USD",
            period_start=state.money.period_start,
            period_end=state.money.period_end,
            observed_at=now,
            expires_at=now + timedelta(minutes=2),
            reporting_watermark=now,
            completeness="complete",
            qualification_id=qualification.qualification_id,
            model_version="controlled_contract_scenario",
            cap_semantics="contract_scenario",
            reported_spend_micros=0,
            unreported_upper_micros=0,
            unchanged_future_upper_micros=0,
            proposed_owner_upper_micros=40000000,
            existing_reservations_micros=held,
            portfolio_upper_micros=held + 40000000,
        )

    native = replace(
        planning.native,
        execution=replace(
            planning.native.execution, qualification_reader=qualify, exposure_reader=exposure
        ),
        initial_planning=planning,
        clock=planning.clock,
    )
    runtime = InitialPreviewReviewRuntime(planning, native)
    with Session(engine) as db:
        user, session = db.get(CustomerUser, actor), db.get(CustomerSession, token)
        assert user and session
        principal = CustomerPrincipal(user, session)
    return wid, document, principal, provider, runtime, server, calls


def historical_contract_qualified_handoff_replay_and_missing_link_do_not_duplicate(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch, replicas: Any
) -> None:
    wid, preview, principal, provider, runtime, server, calls = ready(
        customer_engine, configuration, monkeypatch, replicas
    )
    first = prepare_preview_review(runtime, principal, provider, wid, preview.id, preview.digest())
    assert calls == ["qualification", "exposure"] and not server.posts
    again = prepare_preview_review(runtime, principal, provider, wid, preview.id, preview.digest())
    assert again == first and calls == ["qualification", "exposure"]
    with Session(customer_engine) as db:
        row = db.get(ProviderExecutionReview, first.review_id)
        assert (
            row
            and row.initial_preview_origin_id == preview.id
            and row.initial_preview_provenance_required
        )
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(
                update(ProviderExecutionReview)
                .where(ProviderExecutionReview.id == row.id)
                .values(initial_preview_provenance_required=False, initial_preview_origin_id=None)
            )
        db.execute(
            delete(InitialPreviewReviewLink).where(InitialPreviewReviewLink.review_id == row.id)
        )
        db.commit()
    with pytest.raises(HTTPException, match="retracted"):
        prepare_preview_review(runtime, principal, provider, wid, preview.id, preview.digest())
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderExecutionReview)) == 1


def historical_contract_erased_preview_blocks_generic_approval_without_deleting_review(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch, replicas: Any
) -> None:
    wid, preview, principal, provider, runtime, server, _ = ready(
        customer_engine, configuration, monkeypatch, replicas
    )
    result = prepare_preview_review(runtime, principal, provider, wid, preview.id, preview.digest())
    with Session(customer_engine) as db:
        db.execute(delete(PreviewRow).where(PreviewRow.id == preview.id))
        db.commit()
        link = db.get(InitialPreviewReviewLink, result.review_id)
        assert link and link.preview_id is None
        bound = customer_optimization.bind(runtime.optimization, principal, provider)
        with pytest.raises(HTTPException, match="retracted"):
            optimization.approve_optimization(
                db,
                wid,
                result.review_id,
                result.review_digest,
                result.plan_digest,
                principal.user.id,
                bound.execution,
                runtime.planning.clock,
            )
        assert db.get(ProviderExecutionReview, result.review_id) is not None
        assert not server.posts


@pytest.mark.parametrize("stage", ["approval", "admission", "claim", "emission"])
def historical_contract_every_forward_gate_rechecks_retracted_provenance(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    stage: str,
) -> None:
    wid, preview, principal, provider, runtime, server, _ = ready(
        customer_engine, configuration, monkeypatch, replicas
    )
    result = prepare_preview_review(runtime, principal, provider, wid, preview.id, preview.digest())
    bound = customer_optimization.bind(runtime.optimization, principal, provider)
    clock = runtime.planning.clock
    with Session(customer_engine) as db:
        if stage != "approval":
            optimization.approve_optimization(
                db,
                wid,
                result.review_id,
                result.review_digest,
                result.plan_digest,
                principal.user.id,
                bound.execution,
                clock,
            )
        if stage in {"claim", "emission"}:
            run = optimization.create_run(
                db, wid, result.review_id, principal.user.id, bound.execution, clock
            )
        if stage == "emission":
            claim = optimization.claim_step(
                db, wid, run.id, principal.user.id, bound.execution, clock
            )
            assert claim
        db.execute(delete(PreviewRow).where(PreviewRow.id == preview.id))
        db.commit()
        with pytest.raises(HTTPException, match="retracted"):
            if stage == "approval":
                optimization.approve_optimization(
                    db,
                    wid,
                    result.review_id,
                    result.review_digest,
                    result.plan_digest,
                    principal.user.id,
                    bound.execution,
                    clock,
                )
            elif stage == "admission":
                optimization.create_run(
                    db, wid, result.review_id, principal.user.id, bound.execution, clock
                )
            elif stage == "claim":
                optimization.claim_step(db, wid, run.id, principal.user.id, bound.execution, clock)
            else:
                assert claim is not None
                optimization.execute_claim(db, claim, principal.user.id, bound.execution, clock)
        assert not server.posts


@pytest.mark.parametrize(
    "change",
    ["qualification_missing", "erase_during_qualification", "expired_during_qualification"],
)
def historical_contract_actual_financial_io_never_bypasses_preview_recheck(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    change: str,
) -> None:
    wid, preview, principal, provider, runtime, server, _ = ready(
        customer_engine, configuration, monkeypatch, replicas
    )
    qualify = runtime.optimization.execution.qualification_reader
    clock = [runtime.planning.clock()]

    def changed(*args: Any) -> Any:
        if change == "qualification_missing":
            raise HTTPException(409, "real qualification unavailable")
        if change == "erase_during_qualification":
            with Session(customer_engine) as other:
                other.execute(delete(PreviewRow).where(PreviewRow.id == preview.id))
                other.commit()
        else:
            clock[0] = preview.expires_at
        return qualify(*args)

    runtime = replace(
        runtime,
        planning=replace(runtime.planning, clock=lambda: clock[0]),
        optimization=replace(
            runtime.optimization,
            execution=replace(runtime.optimization.execution, qualification_reader=changed),
        ),
    )
    with pytest.raises(HTTPException):
        prepare_preview_review(runtime, principal, provider, wid, preview.id, preview.digest())
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderExecutionReview)) == 0
    assert not server.posts


def historical_contract_attempt_receipt_hold_and_reconcile_survive_preview_erasure(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> None:
    wid, preview, principal, provider, runtime, server, _ = ready(
        customer_engine, configuration, monkeypatch, replicas
    )
    result = prepare_preview_review(runtime, principal, provider, wid, preview.id, preview.digest())
    bound = customer_optimization.bind(runtime.optimization, principal, provider)
    clock = runtime.planning.clock
    with Session(customer_engine) as db:
        optimization.approve_optimization(
            db,
            wid,
            result.review_id,
            result.review_digest,
            result.plan_digest,
            principal.user.id,
            bound.execution,
            clock,
        )
        run = optimization.create_run(
            db, wid, result.review_id, principal.user.id, bound.execution, clock
        )
        claim = optimization.claim_step(db, wid, run.id, principal.user.id, bound.execution, clock)
        assert claim
        receipt = optimization.execute_claim(db, claim, principal.user.id, bound.execution, clock)
        assert receipt.outcome == "verified_target_state" and len(server.posts) == 1
        db.execute(delete(PreviewRow).where(PreviewRow.id == preview.id))
        db.commit()
        recovered = optimization.reconcile_attempt(
            db, wid, claim.attempt_id, bound.execution, clock
        )
        assert recovered.outcome == "verified_target_state"
        assert len(server.posts) == 1
        reservation = db.get(ProviderExposureReservation, run.reservation_id)
        assert reservation is not None and reservation.state == "held"
        assert (
            optimization.read_owned_outcome_receipt(db, wid, claim.attempt_id, principal.user.id)
            is not None
        )


def historical_contract_concurrent_handoffs_share_protected_origin(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    if customer_engine.dialect.name != "postgresql":
        pytest.skip("requires independent PostgreSQL transactions")
    wid, preview, principal, provider, runtime, server, _ = ready(
        customer_engine, configuration, monkeypatch, replicas
    )
    barrier = Barrier(2)
    qualify = runtime.optimization.execution.qualification_reader

    def synchronized(*args: Any) -> Any:
        barrier.wait(timeout=20)
        return qualify(*args)

    runtime = replace(
        runtime,
        optimization=replace(
            runtime.optimization,
            execution=replace(runtime.optimization.execution, qualification_reader=synchronized),
        ),
    )

    def invoke() -> Any:
        return prepare_preview_review(
            runtime, principal, provider, wid, preview.id, preview.digest()
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(invoke), pool.submit(invoke)
        a, b = first.result(timeout=40), second.result(timeout=40)
    assert a == b and not server.posts
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderExecutionReview)) == 1


def historical_contract_retraction_during_final_provider_io_blocks_emission(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> None:
    wid, preview, principal, provider, runtime, server, _ = ready(
        customer_engine, configuration, monkeypatch, replicas
    )
    result = prepare_preview_review(runtime, principal, provider, wid, preview.id, preview.digest())
    bound = customer_optimization.bind(runtime.optimization, principal, provider)
    clock = runtime.planning.clock
    with Session(customer_engine) as db:
        optimization.approve_optimization(
            db,
            wid,
            result.review_id,
            result.review_digest,
            result.plan_digest,
            principal.user.id,
            bound.execution,
            clock,
        )
        run = optimization.create_run(
            db, wid, result.review_id, principal.user.id, bound.execution, clock
        )
        claim = optimization.claim_step(db, wid, run.id, principal.user.id, bound.execution, clock)
        assert claim
        context = bound.execution.context
        deleted: list[bool] = []

        def during_io(scope):  # type: ignore[no-untyped-def]
            if not deleted:
                with Session(customer_engine) as other:
                    other.execute(delete(PreviewRow).where(PreviewRow.id == preview.id))
                    other.commit()
                deleted.append(True)
            return context(scope)

        changed = replace(bound.execution, context=during_io)
        with pytest.raises(HTTPException, match="retracted"):
            optimization.execute_claim(db, claim, principal.user.id, changed, clock)
        assert deleted and not server.posts


def historical_contract_missing_registered_guard_is_not_manual_authority(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> None:
    wid, preview, principal, provider, runtime, server, _ = ready(
        customer_engine, configuration, monkeypatch, replicas
    )
    result = prepare_preview_review(runtime, principal, provider, wid, preview.id, preview.digest())
    ordinary = customer_optimization.bind(
        replace(runtime.optimization, initial_planning=None), principal, provider
    )
    with (
        Session(customer_engine) as db,
        pytest.raises(HTTPException, match="initial preview review authority unavailable"),
    ):
        optimization.approve_optimization(
            db,
            wid,
            result.review_id,
            result.review_digest,
            result.plan_digest,
            principal.user.id,
            ordinary.execution,
            runtime.planning.clock,
        )
    assert not server.posts


@pytest.mark.parametrize("change", ["missing", "policy"])
def historical_contract_forward_runtime_context_required_before_financial_io(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    change: str,
) -> None:
    wid, preview, principal, provider, runtime, server, calls = ready(
        customer_engine, configuration, monkeypatch, replicas
    )
    context = None
    if change == "policy":
        assert runtime.planning.configuration
        context = replace(
            runtime.planning,
            configuration=runtime.planning.configuration.model_copy(update={"revision": 2}),
        )
    runtime = replace(runtime, optimization=replace(runtime.optimization, initial_planning=context))
    with pytest.raises(HTTPException, match="initial_preview_forward_runtime_unavailable"):
        prepare_preview_review(runtime, principal, provider, wid, preview.id, preview.digest())
    assert not calls and not server.posts
