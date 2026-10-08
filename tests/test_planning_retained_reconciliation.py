"""Historical uncertain effects remain readable with the MVP write policy intact."""

from pathlib import Path

import pytest
from app import advertising_capabilities
from app.advertising_capabilities import AdvertisingWritesDisabled
from app.publication import coordinator as c
from app.publication.execution_models import ProviderExecutionAttempt, ProviderExposureReservation
from app.publication.provider_contracts import ProviderResponse
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_provider_coordinator import GoogleServer, ready
from tests.test_shopify_sales import configuration as configuration


def test_retained_unknown_reconciles_without_new_write_or_releasing_hold(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = GoogleServer()
    server.timeout = True
    with Session(customer_engine) as db:
        # Produce authentic pre-MVP history using existing engines and MockHTTP.
        # The temporary override ends BEFORE the behavior under test.
        with monkeypatch.context() as historical:
            historical.setattr(advertising_capabilities, "require_advertising_write", lambda: None)
            wid, run_id, actor, store, runtime = ready(db, configuration, tmp_path, server)
            claim = c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW)
            assert claim is not None
            assert (
                c.execute_claim(db, claim, actor, store, runtime, lambda: NOW).outcome == "unknown"
            )
        assert advertising_capabilities.advertising_writes_enabled() is False
        with pytest.raises(AdvertisingWritesDisabled):
            advertising_capabilities.require_advertising_write()
        before = [
            dict(r) for r in db.execute(select(ProviderExposureReservation.__table__)).mappings()
        ]
        assert len(before) == 1 and before[0]["state"] == "held"
        c.record_response(
            db,
            wid,
            claim.attempt_id,
            ProviderResponse(
                request_digest=claim.request.digest(),
                outcome="acknowledged",
                resource_name=next(iter(server.rows)),
            ),
            lambda: NOW,
        )
        receipt = c.reconcile_attempt(db, wid, claim.attempt_id, runtime, lambda: NOW)
        assert receipt.outcome == "verified_effect"
        assert server.posts == 1
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 1
        assert [
            dict(r) for r in db.execute(select(ProviderExposureReservation.__table__)).mappings()
        ] == before
        with pytest.raises(AdvertisingWritesDisabled):
            c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW)
        assert server.posts == 1
