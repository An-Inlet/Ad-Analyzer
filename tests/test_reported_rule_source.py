"""Owned real reporting read, no learning/authority label conversion."""

from pathlib import Path

import pytest
from app.publication.execution_models import ProviderExposureReservation
from app.reported_feedback.candidate_source import read_reported_rule
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.reported_rule_fixture import ready_reported_rule
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_shopify_sales import configuration as configuration


def test_actual_owned_reports_read_then_revocation_denies(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with Session(customer_engine) as db:
        principal, identity, work, observation, clock, requests, server = ready_reported_rule(
            db, configuration, tmp_path, monkeypatch
        )
        held = db.scalar(select(ProviderExposureReservation))
        assert held and held.state == "held"
        before = len(requests), len(server.posts), held.amount_micros
        value = read_reported_rule(db, principal, identity, work, observation, lambda: clock[0])
        assert value.evidence.signed_delta_micros == -250_000
        assert value.evidence.reported_completion_count == 4
        assert value.evidence.causal_lift == "unavailable"
        assert before == (len(requests), len(server.posts), held.amount_micros)
        principal.session.revoked_at = int(clock[0].timestamp())
        db.commit()
        with pytest.raises(HTTPException):
            read_reported_rule(db, principal, identity, work, observation, lambda: clock[0])


def test_final_authorization_wait_cannot_extend_report_lifetime(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import timedelta

    from app.customers.access import lock_customer_mutation
    from app.reported_feedback import candidate_source

    with Session(customer_engine) as db:
        principal, identity, work, observation, clock, _, _ = ready_reported_rule(
            db, configuration, tmp_path, monkeypatch
        )
        original = lock_customer_mutation
        checks = 0

        def delayed(*args, **kwargs):  # type: ignore[no-untyped-def]
            nonlocal checks
            original(*args, **kwargs)
            checks += 1
            if checks == 2:
                clock[0] = work.selection.expires_at + timedelta(microseconds=1)

        monkeypatch.setattr(candidate_source, "lock_customer_mutation", delayed)
        with pytest.raises(HTTPException, match="reported_rule_current_evidence_unavailable"):
            read_reported_rule(db, principal, identity, work, observation, lambda: clock[0])
        assert checks == 2
