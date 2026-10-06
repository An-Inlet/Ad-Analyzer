"""Deleted provider objects must not turn historical spend into zero."""

import json
from datetime import timedelta
from typing import Any

import httpx
import pytest
from app.ads.models import Campaign, DailyMetric
from app.api.repository import ReadOnlyAdsRepository
from app.sources import advertising
from app.tiktok.http import TikTokHTTPRead
from pydantic import SecretStr
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_customer_connections import setup
from tests.test_tiktok_sources import TikTokFixture, connect
from tests.test_tiktok_sources import configured as configured


@pytest.mark.parametrize("deleted_phase", ["campaign", "adgroup", "ad", "all"])
def test_deleted_history_survives_paginated_refresh_and_preserves_other_workspace(
    customer_engine: Engine, configured: None, deleted_phase: str
) -> None:
    deleted = False
    requests: list[tuple[str, int]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        query, path = request.url.params, request.url.path
        if path.endswith("advertiser/info/"):
            assert json.loads(query["advertiser_ids"]) == ["123456"]
            data: dict[str, Any] = {"list": [{"advertiser_id": "123456", "currency": "USD"}]}
        else:
            assert query["advertiser_id"] == "123456"
            page = int(query["page"])
            report = path.endswith("report/integrated/get/")
            rows: list[dict[str, Any]]
            if report:
                field = json.loads(query["dimensions"])[0]
                kind = field.removesuffix("_id")
                # The provider fixture reproduces its deleted-excluding default when
                # the appropriate filter is absent, incorrectly shaped or double encoded.
                filters = json.loads(query.get("filtering", "[]"))
                all_status = filters == [
                    {
                        "field_name": kind + "_status",
                        "filter_type": "IN",
                        "filter_value": '["STATUS_ALL"]',
                    }
                ]
                rows = [
                    {
                        "dimensions": {
                            field: {"campaign": "1", "adgroup": "2", "ad": "3"}[kind],
                            "stat_time_day": query["end_date"],
                        },
                        "metrics": {
                            "impressions": "100",
                            "clicks": "10",
                            "spend": "12.34",
                            "conversion": "1.5",
                        },
                    }
                ]
            else:
                kind = path.split("/")[-3]
                all_status = json.loads(query.get("filtering", "{}")) == {
                    "primary_status": "STATUS_ALL"
                }
                rows = (
                    [
                        {
                            "campaign_id": "1",
                            "campaign_name": "Historical campaign",
                            "objective_type": "CONVERSIONS",
                        }
                    ]
                    if kind == "campaign"
                    else (
                        [
                            {
                                "adgroup_id": "2",
                                "campaign_id": "1",
                                "adgroup_name": "Historical group",
                            }
                        ]
                        if kind == "adgroup"
                        else [{"ad_id": "3", "adgroup_id": "2", "ad_name": "Historical ad"}]
                    )
                )
                rows[0]["operation_status"] = "DELETE" if deleted else "ENABLE"
            requests.append((kind, page))
            if page == 1 or (deleted and deleted_phase in {kind, "all"} and not all_status):
                rows = []
            data = {"list": rows, "page_info": {"page": page, "total_page": 2}}
        return httpx.Response(200, json={"code": 0, "data": data})

    runtime = TikTokHTTPRead(
        "1234", SecretStr("fixture-secret"), transport=httpx.MockTransport(handler)
    )
    with Session(customer_engine) as db:
        one, sid = setup(db, "one")
        two, sid2 = setup(db, "two")
        row, _ = connect(db, one, sid, TikTokFixture())
        other, _ = connect(db, two, sid2, TikTokFixture())
        advertising.tick(db, two, other.id, other.generation, TikTokFixture(), NOW)
        advertising.tick(db, two, other.id, other.generation, TikTokFixture(), NOW)
        for refresh in range(2):
            deleted = bool(refresh)
            start, end = row.window_start, row.window_end
            for page in range(12):
                job = advertising.tick(
                    db, one, row.id, row.generation, runtime, NOW + timedelta(minutes=refresh)
                )
                assert (job is None) == (page < 11)
            assert row.account_id is not None
            totals = ReadOnlyAdsRepository(db).account_metric_totals(row.account_id, start, end)
            assert totals["cost_micros"] == 12_340_000
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(DailyMetric)
                    .join(Campaign, DailyMetric.campaign_id == Campaign.id)
                    .where(Campaign.account_id == row.account_id)
                )
                == 3
            )
            assert other.account_id is not None
            assert (
                ReadOnlyAdsRepository(db).account_metric_totals(other.account_id, start, end)[
                    "cost_micros"
                ]
                == 100_000_000
            )
        assert len(requests) == 24
        assert row.error_code is None and row.last_sync_at is not None
