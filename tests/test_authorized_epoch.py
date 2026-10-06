"""Epoch readers receive the real starting session; callback changes cannot grant authority."""

import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerSession
from app.optimization_candidates.contracts import CandidateDecision
from app.publication.execution_models import ProviderExecutionApproval, ProviderExecutionAttempt
from app.session_automation import service, worker
from app.session_automation.contracts import SemanticDecisionEpoch
from app.session_automation.models import AutomaticDecisionAdmission
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_session_automation import automatic_fixture
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("change", ["none", "revoke", "expire", "no_reader"])
def test_authorized_epoch_receives_original_session_and_revalidates_after_callback(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    calls: list[tuple[str, str]] = []
    with Session(customer_engine) as db:
        principal, wid, intent, runtime, server = automatic_fixture(
            db, configuration, tmp_path, "google_ads", monkeypatch
        )
        actor, token = principal.user.id, principal.session.digest
        original_read: Callable[[Session, CandidateDecision], SemanticDecisionEpoch] | None = (
            runtime.epoch_producers[0].read
        )
        assert original_read is not None

        def forbidden(db: Session, decision: CandidateDecision) -> SemanticDecisionEpoch:
            raise AssertionError("legacy reader must not replace authorized reader")

        def authorized(
            db: Session, actual: CustomerPrincipal, decision: CandidateDecision
        ) -> SemanticDecisionEpoch:
            calls.append((actual.user.id, actual.session.digest))
            assert (actual.user.id, actual.session.digest) == (actor, token)
            assert actual.session.user_id == actual.user.id
            assert db.in_transaction()
            value = original_read(db, decision)
            # Controlled change after authorization, before the callback returns.
            # Revalidation must observe it before admitting an epoch or provider claim.
            row = db.get(CustomerSession, token)
            assert row
            if change == "revoke":
                row.revoked_at = int(time.time())
            elif change == "expire":
                row.expires_at = 0
            db.flush()
            return value

        producer = replace(runtime.epoch_producers[0], read=forbidden, authorized_read=authorized)
        runtime = replace(runtime, epoch_producers=(producer,))
        service.start(db, principal, wid, intent, runtime)
        if change == "no_reader":
            runtime = replace(
                runtime, epoch_producers=(replace(producer, read=None, authorized_read=None),)
            )
    outcome = worker.run_due(customer_engine, lambda: runtime)
    assert outcome == {"completed" if change == "none" else "blocked": 1}
    assert bool(calls) is (change != "no_reader")
    assert len(server.writes) == (1 if change == "none" else 0)
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(AutomaticDecisionAdmission)) == (
            1 if change == "none" else 0
        )
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == (
            1 if change == "none" else 0
        )
        assert db.scalar(select(func.count()).select_from(ProviderExecutionApproval)) == 0
