"""Actual raw HTTP publication provenance and pure requested-local-window traffic."""

import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
from app.ads.models import Campaign
from app.campaign_performance.models import PerformanceCompletion
from app.campaign_performance.presence_models import MetricPresenceRow, ReportingSemanticsRow
from app.campaign_performance.presence_storage import read_presence
from app.campaign_performance.range_receipts import read_range_receipt
from app.campaign_performance.raw_range_traffic import store_raw_range_traffic
from app.google_connections import range_publication
from app.planning_documents.context import AccountRef, ReportingWindow
from app.planning_documents.selected_plan_contracts import SelectedCampaignBindingV1
from app.planning_documents.selected_traffic import (
    RawRangeTrafficGraphV1,
    project_raw_range_traffic,
)
from app.planning_documents.source_contracts import SourceFence
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tests.test_google_aggregate_range_http import campaign, metric
from tests.test_google_range_publication_api import (
    configured as configured,
)
from tests.test_google_range_publication_api import (
    counts,
    intent,
    scheduler,
)
from tests.test_google_range_publication_api import (
    customer as customer,
)
from tests.test_google_range_publication_api import (
    customer_engine as customer_engine,
)
from tests.test_google_range_publication_api import (
    range_customer as range_customer,
)
from tests.test_google_range_publication_api import (
    replicas as replicas,
)
from tests.test_selected_customer_api import CustomerFixture


def graph(f: CustomerFixture, request_id: str) -> RawRangeTrafficGraphV1:
    # Test construction is not an owned reader or an authority claim.
    with Session(f.engine) as db:
        receipt = read_range_receipt(db, f.wid, f.aid, request_id)
        completion = db.get(PerformanceCompletion, receipt.completion_id)
        assert completion is not None
        retained = read_presence(db, completion)
        assert retained is not None
        header, facts = retained
        campaigns = db.scalars(
            select(Campaign).where(Campaign.account_id == f.aid).order_by(Campaign.id)
        ).all()
        scope = receipt.final_scope
        account = AccountRef(
            workspace_id=f.wid,
            account_id=f.aid,
            connection_id=scope.connection_id,
            platform="google_ads",
            connection_version="test-version",
        )
        return RawRangeTrafficGraphV1(
            receipt=receipt,
            header=header,
            facts=facts,
            campaigns=tuple(
                SelectedCampaignBindingV1(
                    campaign_id=x.id, native_campaign_id=x.external_campaign_id
                )
                for x in campaigns
            ),
            source_fence=SourceFence(
                account=account,
                source_binding_digest="a" * 64,
                source_revision="test-version",
                privacy_revision=scope.privacy_revision,
            ),
        )


def window(month: int) -> ReportingWindow:
    zone = ZoneInfo("America/New_York")
    return ReportingWindow(
        starts_at=datetime(2026, month, 1, tzinfo=zone),
        ends_at_exclusive=datetime(2026, month + 1, 1, tzinfo=zone),
    )


def full_transport(f: CustomerFixture, *, missing: str | None = None) -> None:
    def handle(req: httpx.Request) -> httpx.Response:
        query = json.loads(req.content)["query"]
        if "FROM customer" in query:
            rows: list[dict[str, Any]] = [
                {
                    "customer": {
                        "id": "1234567890",
                        "resourceName": "customers/1234567890",
                        "currencyCode": "USD",
                        "timeZone": "America/New_York",
                    }
                }
            ]
        elif "metrics." not in query:
            rows = [campaign()]
        else:
            rows = []
            for offset in range(61):
                day = date(2026, 8, 1) + timedelta(days=offset)
                row = metric(day=day.isoformat())
                if day != date(2026, 9, 15):
                    row["metrics"] = {
                        "impressions": "0",
                        "clicks": "0",
                        "costMicros": "0",
                        "conversions": "0",
                        "conversionsValue": "0",
                    }
                if missing:
                    del row["metrics"][missing]
                rows.append(row)
        return httpx.Response(200, json={"results": rows})

    f.runtime = replace(f.runtime, transport=lambda: httpx.MockTransport(handle))


def presence_counts(f: CustomerFixture) -> tuple[int, ...]:
    with Session(f.engine) as db:
        return tuple(
            db.scalar(select(func.count()).select_from(model)) or 0
            for model in (ReportingSemanticsRow, MetricPresenceRow)
        )


def test_actual_full_window_and_explicit_zero(range_customer: CustomerFixture) -> None:
    f = range_customer
    full_transport(f)
    body = intent(f)
    response = f.post("/aggregate-range", body)
    assert response.status_code == 200, response.text
    saved = graph(f, body["request_id"])
    assert presence_counts(f) == (1, 61)
    cid = saved.facts[0].campaign_id
    september = project_raw_range_traffic(saved, campaign_id=cid, requested_window=window(9))
    august = project_raw_range_traffic(saved, campaign_id=cid, requested_window=window(8))
    assert september.clicks.value == 100
    assert september.spend_micros.value == 100_000_000
    assert september.clicks.coverage == "observed_requested_days"
    assert september.returned_days == 30 and september.missing_calendar_days == 0
    assert august.clicks.value == 0 and august.spend_micros.value == 0
    assert august.clicks.coverage == "observed_requested_days"
    assert all(x.selected_conversions.presence == "unsupported" for x in saved.facts)
    assert "selected_conversions" not in september.model_dump()
    # Recompute the entire graph before slicing: August corruption blocks September.
    altered = saved.facts[0].model_copy(
        update={"clicks": saved.facts[0].clicks.model_copy(update={"value": True})}
    )
    with pytest.raises(ValueError):
        project_raw_range_traffic(
            saved.model_copy(update={"facts": (altered, *saved.facts[1:])}),
            campaign_id=cid,
            requested_window=window(9),
        )
    with pytest.raises(ValueError):
        RawRangeTrafficGraphV1.model_validate(
            saved.model_copy(
                update={
                    "header": saved.header.model_copy(
                        update={
                            "producer_contract": "google.v24.campaign-day.metrics-conversions.v1"
                        }
                    )
                }
            )
        )
    # Strict copied graph, metadata, map and cell binding, including unsliced facts.
    for update in (
        {"source_fence": saved.source_fence.model_copy(update={"privacy_revision": 999})},
        {"receipt": saved.receipt.model_copy(update={"manifest_digest": "f" * 64})},
        {"campaigns": (*saved.campaigns, saved.campaigns[0])},
        {"facts": tuple(reversed(saved.facts))},
        {"header": saved.header.model_copy(update={"fact_count": 1})},
        {"header": saved.header.model_copy(update={"pagination_complete": False})},
    ):
        with pytest.raises(ValueError):
            RawRangeTrafficGraphV1.model_validate(saved.model_copy(update=update))
    with pytest.raises(ValueError):
        project_raw_range_traffic(saved, campaign_id=True, requested_window=window(9))
    with pytest.raises(ValueError):
        project_raw_range_traffic(saved, campaign_id=cid, requested_window=window(7))
    with pytest.raises(ValueError):
        project_raw_range_traffic(
            saved,
            campaign_id=cid,
            requested_window=window(9).model_copy(
                update={"starts_at": window(9).starts_at.timestamp()}
            ),
        )
    utc_window = ReportingWindow(
        starts_at=window(9).starts_at.astimezone(UTC),
        ends_at_exclusive=window(9).ends_at_exclusive.astimezone(UTC),
    )
    assert (
        project_raw_range_traffic(saved, campaign_id=cid, requested_window=utc_window) == september
    )
    # Later range import invalidates current receipt but never mutates saved evidence.
    later = f.post("/aggregate-range", intent(f))
    assert later.status_code == 200, later.text
    with Session(f.engine) as db:
        assert (
            read_range_receipt(db, f.wid, f.aid, body["request_id"], require_current=False)
            == saved.receipt
        )
        completion = db.get(PerformanceCompletion, saved.receipt.completion_id)
        assert completion is not None
        assert read_presence(db, completion) == (saved.header, saved.facts)
    assert (
        project_raw_range_traffic(saved, campaign_id=cid, requested_window=window(9)) == september
    )


def test_sparse_rows_remain_partial_and_absence_not_zero(range_customer: CustomerFixture) -> None:
    f = range_customer
    body = intent(f)
    assert f.post("/aggregate-range", body).status_code == 200
    saved = graph(f, body["request_id"])
    cid = saved.facts[0].campaign_id
    for month in (8, 9):
        result = project_raw_range_traffic(saved, campaign_id=cid, requested_window=window(month))
        assert result.clicks.value == 100 and result.clicks.coverage == "partial"
        assert result.returned_days == 1
    # An actually acquired subwindow with no returned rows is unavailable, not zero.
    absent_window = ReportingWindow(
        starts_at=datetime(2026, 8, 2, tzinfo=ZoneInfo("America/New_York")),
        ends_at_exclusive=datetime(2026, 9, 1, tzinfo=ZoneInfo("America/New_York")),
    )
    projected = project_raw_range_traffic(saved, campaign_id=cid, requested_window=absent_window)
    assert projected.clicks.value is None and projected.clicks.coverage == "unavailable"
    assert projected.missing_calendar_days == 30


def test_sidecar_failure_rolls_back_whole_publication(
    range_customer: CustomerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    f = range_customer
    before, scheduled, sidecars = counts(f), scheduler(f), presence_counts(f)
    original = store_raw_range_traffic

    def fail(*args: Any, **kwargs: Any) -> None:
        original(*args, **kwargs)
        raise ValueError("after actual sidecar insert")

    monkeypatch.setattr(range_publication, "store_raw_range_traffic", fail)
    response = f.post("/aggregate-range", intent(f))
    assert response.status_code == 409, response.text
    assert counts(f) == before and scheduler(f) == scheduled and presence_counts(f) == sidecars


def test_old_receipt_never_backfilled(
    range_customer: CustomerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    f = range_customer
    body = intent(f)
    with monkeypatch.context() as patch:
        patch.setattr(range_publication, "store_raw_range_traffic", lambda *args, **kwargs: None)
        response = f.post("/aggregate-range", body)
        assert response.status_code == 200, response.text
    assert presence_counts(f) == (0, 0)
    assert f.post("/aggregate-range", body).json() == response.json()
    assert presence_counts(f) == (0, 0)


@pytest.mark.parametrize(
    "cell", ["clicks", "impressions", "costMicros", "conversions", "conversionsValue"]
)
def test_missing_raw_cell_never_publishes(range_customer: CustomerFixture, cell: str) -> None:
    f = range_customer
    full_transport(f, missing=cell)
    before = counts(f)
    response = f.post("/aggregate-range", intent(f))
    assert response.status_code == 409, response.text
    assert counts(f) == before and presence_counts(f) == (0, 0)


def test_populated_export_and_raw_delete_revoke_currentness(
    range_customer: CustomerFixture,
) -> None:
    from app.campaign_performance.presence_storage import ReportingPresenceUnavailable
    from app.campaign_performance.selected_storage import SelectedReportingUnavailable
    from app.lifecycle.contracts import LifecycleScopeV1
    from app.lifecycle.inventory import export_section
    from app.lifecycle.privacy import bump_workspace_export_revision
    from sqlalchemy import delete

    f = range_customer
    body = intent(f)
    assert f.post("/aggregate-range", body).status_code == 200
    saved = graph(f, body["request_id"])
    with Session(f.engine) as db:
        for model in (ReportingSemanticsRow, MetricPresenceRow):
            exported = export_section(db, LifecycleScopeV1(workspace_id=f.wid), model.__tablename__)
            assert exported
        db.execute(
            delete(MetricPresenceRow).where(
                MetricPresenceRow.completion_id == saved.receipt.completion_id
            )
        )
        db.commit()
        # Raw fact loss corrupts traffic provenance, not the independent generic receipt.
        assert read_range_receipt(db, f.wid, f.aid, body["request_id"]) == saved.receipt
        completion = db.get(PerformanceCompletion, saved.receipt.completion_id)
        assert completion is not None
        with pytest.raises(ReportingPresenceUnavailable):
            read_presence(db, completion)
        bump_workspace_export_revision(db, f.wid)
        db.commit()
        with pytest.raises(SelectedReportingUnavailable):
            read_range_receipt(db, f.wid, f.aid, body["request_id"])
        assert read_presence(db, completion) is None
    # Pure retained data remains as-observed, not authorization to bypass erasure.
    assert RawRangeTrafficGraphV1.model_validate(saved) == saved
