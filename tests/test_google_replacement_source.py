"""Real captured Google originals + explicitly synthetic financial source, never live proof."""

from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from app.google_connections.models import GoogleCustomerConnection
from app.publication import optimization as o
from app.publication import replacement as r
from app.publication.execution_authorization import owner_authorizer
from app.publication.execution_models import ProviderExposureReservation, ProviderPeriodLedger
from app.publication.google_replacement_source import GoogleReplacementReader
from app.publication.replacement_contracts import RepeatOptimizationReview
from app.publication.transition_source_contracts import TransitionCertificate, TransitionProfile
from app.settings import Settings
from app.workspaces.models import WorkspaceMembership
from fastapi import HTTPException
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_request_terminal import chain
from tests.test_repeat_optimization import reader
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "changed",
        "session",
        "role",
        "generation",
        "highwater",
        "unavailable",
        "http_error",
        "holds",
        "null",
        "profile",
        "future",
        "expired",
        "authorization_delay",
        "scope",
    ],
)
def test_composition_prepare_and_transfer(
    customer_engine: Engine, configuration: Settings, tmp_path: Path, failure: str | None
) -> None:
    with Session(customer_engine) as db:
        wid, actor, binding, snapshot, runtime, target, action = chain(db, configuration, tmp_path)
        clock = [NOW]
        state: dict[str, Any] = {"certificate": None, "deny": False, "recheck": False}

        def authorize(session: Session, workspace: int, principal: str) -> None:
            owner_authorizer(session, workspace, principal)
            if state.get("delay"):
                clock[0] = NOW + timedelta(minutes=10)
            if state["deny"]:
                raise HTTPException(403, "current session unavailable")

        def source(request: Any, now: Any) -> TransitionCertificate:
            if state["certificate"] is None:
                with Session(customer_engine) as independent:
                    proof = reader(runtime)(
                        independent,
                        request.binding,
                        request.intent,
                        request.before,
                        request.qualification,
                        request.snapshot,
                        NOW,
                    )
                state["certificate"] = TransitionCertificate(
                    request_digest=request.digest(),
                    source_profile="offline_transition",
                    source_revision=1,
                    source_evidence_digest="a" * 64,
                    observed_at=NOW,
                    expires_at=proof.portfolio.expires_at,
                    semantics="current_proposed_delayed_no_effect_and_residual",
                    portfolio=proof.portfolio,
                )
            certificate = state["certificate"]
            assert isinstance(certificate, TransitionCertificate)
            if state["recheck"]:
                if failure == "changed":
                    certificate = certificate.model_copy(
                        update={"source_evidence_digest": "b" * 64}
                    )
                elif failure == "session":
                    state["deny"] = True
                elif failure == "role":
                    with Session(customer_engine) as external:
                        membership = external.scalar(
                            select(WorkspaceMembership).where(
                                WorkspaceMembership.workspace_id == wid,
                                WorkspaceMembership.principal == actor,
                            )
                        )
                        assert membership is not None
                        membership.role = "viewer"
                        external.commit()
                elif failure in {"generation", "highwater"}:
                    with Session(customer_engine) as external:
                        if failure == "generation":
                            row = external.scalar(
                                select(GoogleCustomerConnection).where(
                                    GoogleCustomerConnection.workspace_id == wid
                                )
                            )
                            assert row is not None
                            row.generation += 1
                        else:
                            ledger = external.get(ProviderPeriodLedger, binding.ledger_id)
                            assert ledger is not None
                            ledger.spent_high_water_micros += 1
                        external.commit()
                elif failure == "unavailable":
                    raise RuntimeError("private-provider-payload")
                elif failure == "http_error":
                    raise HTTPException(502, "private-provider-payload")
                elif failure == "holds":
                    with Session(customer_engine) as external:
                        external.add(
                            ProviderExposureReservation(
                                id="f" * 32,
                                workspace_id=wid,
                                ledger_id=binding.ledger_id,
                                environment="contract_test",
                                budget_owner_key="another-owner",
                                amount_micros=1,
                                state="held",
                                evidence={},
                            )
                        )
                        external.commit()
                elif failure == "null":
                    e = certificate.portfolio.model_copy(
                        update={"unreported_upper_micros": None, "portfolio_upper_micros": None}
                    )
                    certificate = certificate.model_copy(update={"portfolio": e})
                elif failure == "profile":
                    certificate = certificate.model_copy(update={"source_profile": "not-allowed"})
                elif failure == "future":
                    certificate = certificate.model_copy(
                        update={"observed_at": NOW + timedelta(seconds=30)}
                    )
                elif failure == "authorization_delay":
                    state["delay"] = True
                elif failure == "expired":
                    clock[0] = NOW + timedelta(minutes=10)
                elif failure == "scope":
                    certificate = certificate.model_copy(update={"request_digest": "f" * 64})
            return certificate

        # Every profile and financial bound here is explicitly contract-test-only.
        original_reader = runtime.qualification_reader
        with Session(customer_engine) as independent:
            q = original_reader(independent, binding, snapshot.account, target, NOW)
        compositor = GoogleReplacementReader(
            lambda: Session(customer_engine),
            actor,
            authorize,
            source,
            {
                ("offline_transition", 1): TransitionProfile(
                    environment="contract_test",
                    qualification_profile=q.profile,
                    qualification_revision=q.qualification_revision,
                    proof_kind="contract_scenario",
                    cap_semantics="contract_scenario",
                    model_version="controlled_contract_scenario",
                )
            },
            lambda: clock[0],
        )
        # Fixture model identifier comes from the existing explicitly synthetic exposure reader.
        action = action.model_copy(update={"amount_micros": 43_000_000})
        composed = replace(runtime, replacement_reader=compositor)
        row = r.prepare_repeat_optimization(
            db,
            wid,
            binding,
            snapshot.account,
            snapshot.predecessor_id,
            target,
            action,
            "c" * 64,
            actor,
            composed,
            lambda: clock[0],
        )
        document = RepeatOptimizationReview.model_validate(row.document)
        o.approve_optimization(
            db, wid, row.id, row.digest, row.plan_digest, actor, composed, lambda: clock[0]
        )
        run = o.create_run(db, wid, row.id, actor, composed, lambda: clock[0])
        state["recheck"] = True
        clock[0] += timedelta(seconds=1)
        if failure is not None:
            with pytest.raises(HTTPException) as error:
                if failure == "authorization_delay":
                    # Assert the source itself rejects, not just the coordinator's later gate.
                    compositor(
                        db,
                        binding,
                        document.plan.intent,
                        document.plan.before,
                        document.plan.qualification,
                        document.predecessor,
                        clock[0],
                    )
                else:
                    r.transfer(db, wid, run, document, actor, composed, lambda: clock[0])
            assert "private-provider-payload" not in str(error.value.detail)
            db.rollback()
            old = db.get(ProviderExposureReservation, snapshot.predecessor_id)
            assert old is not None and old.state == "held"
            assert run.reservation_id is None
        else:
            r.transfer(db, wid, run, document, actor, composed, lambda: clock[0])
            old = db.get(ProviderExposureReservation, snapshot.predecessor_id)
            assert old is not None and old.state == "superseded"
            assert run.reservation_id is not None
            successor = db.get(ProviderExposureReservation, run.reservation_id)
            assert successor is not None and successor.state == "held"
            assert document.replacement.observed_at == NOW


def test_unknown_ancestor_never_calls_financial_source(
    customer_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    with Session(customer_engine) as db:
        wid, actor, binding, snapshot, runtime, target, action = chain(
            db, configuration, tmp_path, timeout=True
        )
        calls = []

        def unavailable(request: Any, now: Any) -> TransitionCertificate:
            calls.append(request)
            raise AssertionError("unknown original must stop before financial source")

        compositor = GoogleReplacementReader(
            lambda: Session(customer_engine), actor, owner_authorizer, unavailable, {}, lambda: NOW
        )
        composed = replace(runtime, replacement_reader=compositor)
        with pytest.raises(HTTPException, match="original response evidence unavailable"):
            r.prepare_repeat_optimization(
                db,
                wid,
                binding,
                snapshot.account,
                snapshot.predecessor_id,
                target,
                action.model_copy(update={"amount_micros": 43_000_000}),
                "c" * 64,
                actor,
                composed,
                lambda: NOW,
            )
        assert calls == []
        old = db.get(ProviderExposureReservation, snapshot.predecessor_id)
        assert old is not None and old.state == "held"
