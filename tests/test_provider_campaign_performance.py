"""Actual Google/TikTok HTTP → terminal import → owned v2 reporting evidence."""

import json
import re
from datetime import timedelta
from typing import Any

import httpx
import pytest
from app.ads.models import Campaign
from app.campaign_performance import service as evidence
from app.campaign_performance.aggregate import descriptor
from app.campaign_performance.contracts import CampaignPerformanceV2
from app.campaign_performance.models import CurrentPerformance
from app.customers.models import CustomerMembership, CustomerSession
from app.google_connections import service as google
from app.sources import advertising
from fastapi import HTTPException
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_execution_session_authorizer import guard
from tests.test_google_customer_connections import FixtureTransport, connect, setup
from tests.test_google_customer_connections import configured as google_configured  # noqa: F401
from tests.test_google_http_runtime import TOKEN, runtime
from tests.test_tiktok_http_runtime import META, adapter, response
from tests.test_tiktok_sources import TikTokFixture
from tests.test_tiktok_sources import configured as tiktok_configured  # noqa: F401
from tests.test_tiktok_sources import connect as connect_tiktok

pytestmark = pytest.mark.usefixtures("google_configured", "tiktok_configured")


def prepared(db: Session, provider: str) -> Any:
    wid, sid = setup(db, provider)
    original = db.get(CustomerSession, sid)
    assert original
    actor = original.user_id
    db.add(CustomerMembership(workspace_id=wid, user_id=actor, role="owner"))
    db.commit()
    auth, _ = guard(db, actor)
    row: Any
    if provider == "google":
        row, _ = connect(db, wid, sid, FixtureTransport())
    else:
        row, _ = connect_tiktok(db, wid, sid, TikTokFixture())
    return row, actor, auth


def google_wire() -> Any:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json=TOKEN)
        assert request.url.host == "googleads.googleapis.com"
        query = json.loads(request.content)["query"]
        if "segments.date" in query:
            dates = re.findall(r"\d{4}-\d{2}-\d{2}", query)
            rows = [
                {
                    "campaign": {"id": "1"},
                    "segments": {"date": dates[0]},
                    "metrics": {
                        "impressions": "100",
                        "clicks": "10",
                        "costMicros": "100000000",
                        "conversions": "0",
                        "conversionsValue": "0",
                    },
                }
            ]
        else:
            rows = [
                {
                    "campaign": {
                        "id": "1",
                        "name": "Campaign",
                        "status": "ENABLED",
                        "advertisingChannelType": "SEARCH",
                    }
                }
            ]
        return httpx.Response(200, json={"results": rows})

    return runtime(handler)


def tiktok_wire() -> Any:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "business-api.tiktok.com"
        rows: list[dict[str, Any]]
        path = request.url.path
        if path.endswith("advertiser/info/"):
            return response({"list": [META]})
        if path.endswith("campaign/get/"):
            rows = [
                {
                    "campaign_id": "1",
                    "campaign_name": "Campaign",
                    "operation_status": "ENABLE",
                    "objective_type": "CONVERSIONS",
                }
            ]
        elif path.endswith("adgroup/get/"):
            rows = [
                {
                    "adgroup_id": "2",
                    "campaign_id": "1",
                    "adgroup_name": "Group",
                    "operation_status": "ENABLE",
                }
            ]
        elif path.endswith("ad/get/"):
            rows = [
                {"ad_id": "3", "adgroup_id": "2", "ad_name": "Ad", "operation_status": "ENABLE"}
            ]
        else:
            dim = json.loads(request.url.params["dimensions"])[0]
            identifier = {"campaign_id": "1", "adgroup_id": "2", "ad_id": "3"}[dim]
            rows = [
                {
                    "dimensions": {
                        dim: identifier,
                        "stat_time_day": request.url.params["end_date"],
                    },
                    "metrics": {
                        "impressions": "100",
                        "clicks": "10",
                        "spend": "100",
                        "conversion": "1.5",
                    },
                }
            ]
        return response({"list": rows, "page_info": {"page": 1, "total_page": 1}})

    return adapter(handler)


@pytest.mark.parametrize("provider", ["google", "tiktok"])
def test_actual_report_completion_and_unknown_adapter_invalidation(
    customer_engine: Engine,
    provider: str,
) -> None:
    with Session(customer_engine) as db:
        source, actor, auth = prepared(db, provider)
        transport = google_wire() if provider == "google" else tiktok_wire()
        tick: Any = google.tick if provider == "google" else advertising.tick
        start, end = source.window_start, source.window_end
        for _index in range(2 if provider == "google" else 6):
            result = tick(db, source.workspace_id, source.id, source.generation, transport, NOW)
            if result is None:
                assert db.get(CurrentPerformance, source.account_id) is None
        assert result is not None
        campaign = db.scalar(select(Campaign).where(Campaign.account_id == source.account_id))
        assert campaign
        value = evidence.read_current(
            db, source.workspace_id, actor, source.account_id, campaign.id, None, auth
        )
        assert isinstance(value, CampaignPerformanceV2)
        assert (value.starts_on, value.ends_on) == (start, end)
        assert value.spend_micros == 100000000 and value.reported_day_count == 1
        if provider == "google":
            assert source.window_end < start  # Next historical window is not current coverage.
            assert value.conversions == "0.000000" and value.conversion_value_micros == 0
            assert value.reported_generic_conversions is None and value.cpa_micros is None
        else:
            assert value.conversions is None and value.conversion_value_micros is None
            assert value.reported_generic_conversions == "1.500000"
            assert value.reported_roas is None and value.cpa_micros is None
        with pytest.raises(HTTPException):
            evidence.read_current(
                db, source.workspace_id + 1, actor, source.account_id, campaign.id, None, auth
            )
        db.commit()

        # Same concrete source but an unqualified arbitrary adapter must not leave
        # old completion authority behind even if a provider returns equal values.
        class UnknownForwarder:
            mode = "fixture"

            def __getattr__(self, name: str) -> Any:
                return getattr(transport, name)

        fallback = UnknownForwarder()
        assert descriptor(fallback) is None  # Claimed property is not authority.
        source.window_start, source.window_end = start, end
        db.commit()
        for _ in range(2 if provider == "google" else 6):
            tick(
                db,
                source.workspace_id,
                source.id,
                source.generation,
                fallback,
                NOW + timedelta(minutes=1),
            )
        assert db.get(CurrentPerformance, source.account_id, populate_existing=True) is None
        from app.ads.models import AdvertisingAccount

        account = db.get(AdvertisingAccount, source.account_id)
        assert account
        assert evidence.manifest(db, account, start, end)[0] == value.manifest_digest
        with pytest.raises(HTTPException):
            evidence.read_current(
                db,
                source.workspace_id,
                actor,
                source.account_id,
                campaign.id,
                value.completion_id,
                auth,
            )


@pytest.mark.parametrize("provider", ["google", "tiktok"])
def test_mixed_query_adapter_pages_and_reconnect_fail_closed(
    customer_engine: Engine,
    provider: str,
) -> None:
    with Session(customer_engine) as db:
        source, _, _ = prepared(db, provider)
        transport = google_wire() if provider == "google" else tiktok_wire()
        tick: Any = google.tick if provider == "google" else advertising.tick
        assert tick(db, source.workspace_id, source.id, source.generation, transport, NOW) is None
        fallback = FixtureTransport() if provider == "google" else TikTokFixture()
        with pytest.raises(HTTPException):
            tick(db, source.workspace_id, source.id, source.generation, fallback, NOW)
        assert db.get(CurrentPerformance, source.account_id) is None
        old = source.generation
        source.generation += 1
        db.commit()
        with pytest.raises(HTTPException):
            tick(db, source.workspace_id, source.id, old, transport, NOW)


@pytest.mark.parametrize("provider", ["google", "tiktok"])
@pytest.mark.parametrize(
    "change", ["generation", "privacy", "metric", "session", "native_identity", "integration"]
)
def test_completed_report_current_fences(
    customer_engine: Engine,
    provider: str,
    change: str,
) -> None:
    import time

    from app.ads.models import AdvertisingAccount, DailyMetric
    from app.lifecycle.privacy import bump_workspace_export_revision

    with Session(customer_engine) as db:
        source, actor, auth = prepared(db, provider)
        transport = google_wire() if provider == "google" else tiktok_wire()
        tick: Any = google.tick if provider == "google" else advertising.tick
        for _ in range(2 if provider == "google" else 6):
            tick(db, source.workspace_id, source.id, source.generation, transport, NOW)
        campaign = db.scalar(select(Campaign).where(Campaign.account_id == source.account_id))
        assert campaign
        value = evidence.read_current(
            db, source.workspace_id, actor, source.account_id, campaign.id, None, auth
        )
        db.commit()
        if change == "generation":
            source.generation += 1
        elif change == "privacy":
            bump_workspace_export_revision(db, source.workspace_id)
        elif change == "metric":
            metric = db.scalar(select(DailyMetric).where(DailyMetric.entity_type == "campaign"))
            assert metric
            metric.clicks += 1
        elif change == "native_identity":
            account = db.get(AdvertisingAccount, source.account_id)
            assert account
            account.external_account_id = "9876543210"
        elif change == "integration":
            from app.workspaces.models import WorkspaceIntegration

            connection = db.get(WorkspaceIntegration, source.integration_id)
            assert connection
            connection.status = "revoked"
        else:
            for session in db.scalars(
                select(CustomerSession).where(CustomerSession.user_id == actor)
            ):
                session.revoked_at = int(time.time())
        db.commit()
        with pytest.raises(HTTPException):
            evidence.read_current(
                db,
                source.workspace_id,
                actor,
                source.account_id,
                campaign.id,
                value.completion_id,
                auth,
            )


@pytest.mark.parametrize("provider", ["google", "tiktok"])
def test_corrected_same_window_replaces_reference_and_overflow_rolls_back(
    customer_engine: Engine,
    provider: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with Session(customer_engine) as db:
        source, actor, auth = prepared(db, provider)
        transport = google_wire() if provider == "google" else tiktok_wire()
        tick: Any = google.tick if provider == "google" else advertising.tick
        start, end = source.window_start, source.window_end
        for _ in range(2 if provider == "google" else 6):
            tick(db, source.workspace_id, source.id, source.generation, transport, NOW)
        campaign = db.scalar(select(Campaign).where(Campaign.account_id == source.account_id))
        assert campaign
        before = evidence.read_current(
            db, source.workspace_id, actor, source.account_id, campaign.id, None, auth
        )
        db.commit()
        source.window_start, source.window_end = start, end
        db.commit()
        later = NOW + timedelta(minutes=1)
        for _ in range(2 if provider == "google" else 6):
            tick(db, source.workspace_id, source.id, source.generation, transport, later)
        after = evidence.read_current(
            db, source.workspace_id, actor, source.account_id, campaign.id, None, auth
        )
        assert (
            after.completion_id != before.completion_id
            and after.manifest_digest == before.manifest_digest
        )
        with pytest.raises(HTTPException):
            evidence.read_current(
                db,
                source.workspace_id,
                actor,
                source.account_id,
                campaign.id,
                before.completion_id,
                auth,
            )
        db.commit()
        source.window_start, source.window_end = start, end
        db.commit()
        for _ in range(1 if provider == "google" else 5):
            tick(db, source.workspace_id, source.id, source.generation, transport, later)
        monkeypatch.setattr(evidence, "MAX_ROWS", 0)
        with pytest.raises(ValueError):
            tick(db, source.workspace_id, source.id, source.generation, transport, later)
        db.rollback()
        current = db.get(CurrentPerformance, source.account_id, populate_existing=True)
        assert current is not None and current.completion_id == after.completion_id


@pytest.mark.parametrize("provider", ["google", "tiktok"])
def test_legacy_staged_pages_finish_without_acquiring_provenance(
    customer_engine: Engine,
    provider: str,
) -> None:
    with Session(customer_engine) as db:
        source, _, _ = prepared(db, provider)
        transport = google_wire() if provider == "google" else tiktok_wire()
        tick: Any = google.tick if provider == "google" else advertising.tick
        assert tick(db, source.workspace_id, source.id, source.generation, transport, NOW) is None
        legacy = dict(source.staged)
        del legacy["performance_contract"]
        source.staged = legacy
        db.commit()
        for _ in range(1 if provider == "google" else 5):
            result = tick(db, source.workspace_id, source.id, source.generation, transport, NOW)
        assert result is not None and source.last_sync_at is not None
        assert db.get(CurrentPerformance, source.account_id) is None
