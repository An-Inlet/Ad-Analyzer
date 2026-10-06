"""Actual persisted terminal imports on both databases, never qualified maturity."""

from datetime import timedelta

import pytest
from app.commerce.models import CommerceMeasurementPublication
from app.commerce.sync import CommerceSyncService
from app.outcomes.reconciliation import collect_owned_reconciliations
from app.outcomes.reconciliation_contracts import ReconciliationRequest
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW, FakeMeasurement, source
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_descriptive_comparisons import prepared
from tests.test_shopify_sales import configuration as configuration


def test_terminal_observations_capture_revisions_without_maturity(
    customer_engine: Engine,
    configuration: Settings,
) -> None:
    configuration = configuration.model_copy(update={"shopify_sync_interval_minutes": 15})
    with Session(customer_engine) as db:
        wid, original = prepared(db, configuration)
        request = ReconciliationRequest(
            goal_id=original.goal_id,
            expected_goal_revision=1,
            latest_publication_id=original.publication_id,
            start=original.before_start,
            end=original.after_end,
        )
        calls = []
        one = collect_owned_reconciliations(
            db, wid, request, lambda: calls.append(True), lambda: NOW
        )
        assert len(calls) == 2 and len(one.observations) == 1
        assert all(day.status == "insufficient_observations" for day in one.days)
        for index in range(1, 18):
            later = NOW + timedelta(minutes=15 * index)
            client = FakeMeasurement(configuration, [([source(updated=later)], None)])
            if index >= 16:
                client.facts[0]["sales"][0]["totalAmount"]["shopMoney"]["amount"] = "109"
            assert (
                CommerceSyncService(db, configuration, client).page(wid, now=later)["status"]
                == "complete"
            )
        latest = db.scalar(
            select(CommerceMeasurementPublication).order_by(
                CommerceMeasurementPublication.publication_revision.desc()
            )
        )
        assert latest
        request = request.model_copy(update={"latest_publication_id": latest.id})
        report = collect_owned_reconciliations(db, wid, request, lambda: None, lambda: later)
        assert report.truncated and len(report.observations) == 16
        assert len({item.completion_digest for item in report.observations}) == 16
        changed = [day for day in report.days if day.changed_pairs]
        assert len(changed) == 1 and changed[0].changed_pairs == 1
        assert changed[0].maximum_absolute_value_change_micros == 10_000_000
        assert changed[0].last_change_observed_at == NOW + timedelta(minutes=15 * 16)
        assert changed[0].last_change_discovery_lag_seconds is not None
        assert changed[0].last_change_discovery_lag_seconds > 0
        assert report.maturity == report.independent_reconciliation == "unqualified"
        assert report.recommendation_update is None and report.spending_authority == "none"
        assert all(item.observation.coverage.mature_through is None for item in report.observations)
        assert not db.new and not db.dirty and not db.deleted
        with pytest.raises(HTTPException) as stale:
            collect_owned_reconciliations(
                db,
                wid,
                request.model_copy(update={"latest_publication_id": original.publication_id}),
                lambda: None,
                lambda: later,
            )
        assert stale.value.status_code == 409
        with pytest.raises(HTTPException) as foreign:
            collect_owned_reconciliations(db, wid + 999, request, lambda: None, lambda: later)
        assert foreign.value.status_code == 404
        tomorrow = NOW + timedelta(days=1)
        client = FakeMeasurement(configuration, [([source(updated=tomorrow)], None)])
        assert (
            CommerceSyncService(db, configuration, client).page(wid, now=tomorrow)["status"]
            == "complete"
        )
        newest = db.scalar(
            select(CommerceMeasurementPublication).order_by(
                CommerceMeasurementPublication.publication_revision.desc()
            )
        )
        assert newest
        expired = collect_owned_reconciliations(
            db,
            wid,
            request.model_copy(update={"latest_publication_id": newest.id}),
            lambda: None,
            lambda: tomorrow,
        )
        assert expired.unreadable_observations == 15 and len(expired.observations) == 1
        assert all(day.status == "insufficient_observations" for day in expired.days)


def test_fresh_authorization_and_revision_are_required(
    customer_engine: Engine, configuration: Settings
) -> None:
    with Session(customer_engine) as db:
        wid, original = prepared(db, configuration)
        request = ReconciliationRequest(
            goal_id=original.goal_id,
            expected_goal_revision=2,
            latest_publication_id=original.publication_id,
            start=original.before_start,
            end=original.after_end,
        )
        with pytest.raises(HTTPException) as error:
            collect_owned_reconciliations(db, wid, request, lambda: None, lambda: NOW)
        assert error.value.status_code == 409
        calls = []

        def revoked() -> None:
            calls.append(True)
            if len(calls) == 2:
                raise HTTPException(401, "session revoked")

        with pytest.raises(HTTPException) as error:
            collect_owned_reconciliations(
                db,
                wid,
                request.model_copy(update={"expected_goal_revision": 1}),
                revoked,
                lambda: NOW,
            )
        assert error.value.status_code == 401


@pytest.mark.parametrize("fault", ["missing", "completion", "privacy"])
def test_missing_is_not_stable_zero_and_bad_lineage_is_rejected(
    customer_engine: Engine,
    configuration: Settings,
    fault: str,
) -> None:
    from app.commerce.evidence import digest
    from app.shopify.privacy import process_event

    from tests.test_shopify_sales import SHOP

    with Session(customer_engine) as db:
        wid, original = prepared(db, configuration)
        request = ReconciliationRequest(
            goal_id=original.goal_id,
            expected_goal_revision=1,
            latest_publication_id=original.publication_id,
            start=original.before_start,
            end=original.after_end,
        )
        row = db.get(CommerceMeasurementPublication, original.publication_id)
        assert row
        if fault == "privacy":
            process_event(db, configuration, "orders/delete", SHOP, {"id": 1}, NOW)
        elif fault == "completion":
            row.completion_digest = "0" * 64
            db.commit()
        else:
            manifest = dict(row.manifest)
            manifest["partitions"] = [
                {**p, "state": "missing", "net_sales_micros": None, "entry_count": None}
                if p["day"] == request.start.isoformat()
                else p
                for p in manifest["partitions"]
            ]
            row.manifest = manifest
            row.manifest_digest = digest(manifest)
            db.commit()
            result = collect_owned_reconciliations(db, wid, request, lambda: None, lambda: NOW)
            assert result.days[0].status == "insufficient_observations"
            assert result.observations[0].observation.value is None
            assert not result.observations[0].observation.coverage.complete
            return
        with pytest.raises(HTTPException) as error:
            collect_owned_reconciliations(db, wid, request, lambda: None, lambda: NOW)
        assert error.value.status_code == (404 if fault == "privacy" else 409)
