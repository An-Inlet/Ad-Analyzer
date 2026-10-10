"""Declared native/reporting bootstrap; actual bounded HTTP adapters read these facts."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import httpx
import pytest
from app.ads.models import AdvertisingAccount, Campaign, DailyMetric
from app.campaign_performance.models import CurrentPerformance, PerformanceCompletion
from app.campaign_performance.service import manifest
from app.collectors import account_diagnostics
from app.google_connections.models import GoogleCustomerConnection
from app.google_connections.security import Vault as GoogleVault
from app.lifecycle.privacy import workspace_export_revision
from app.mandates.schemas import AccountScope
from app.meta.models import MetaConnection
from app.meta.security import API_VERSION
from app.meta.security import Vault as MetaVault
from app.settings import settings
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.test_google_native_inventory import key, payloads
from tests.test_meta_native_inventory import PRIVATE, Server


def install_native_wire(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    for attr in ("google_customer_encryption_key", "meta_token_encryption_key"):
        monkeypatch.setattr(settings, attr, SecretStr(Fernet.generate_key().decode()))
    monkeypatch.setattr(settings, "google_customer_client_id", "synthetic-client")
    monkeypatch.setattr(settings, "google_customer_client_secret", SecretStr("synthetic-secret"))
    monkeypatch.setattr(settings, "meta_client_secret", SecretStr("synthetic-app-secret"))
    monkeypatch.setattr(settings, "customer_native_diagnostics_enabled", True)
    server = Server()
    calls: list[str] = []

    def wire(req: httpx.Request) -> httpx.Response:
        calls.append(req.url.host)
        if req.url.host == "oauth2.googleapis.com":
            return httpx.Response(
                200, json=dict(access_token=PRIVATE, token_type="Bearer", expires_in=3600)
            )
        if req.url.host == "googleads.googleapis.com":
            assert req.method == "POST" and req.url.path.endswith(":search")
            query = json.loads(req.content)["query"]
            data = payloads()
            data["customer"][0]["customer"]["timeZone"] = "UTC"
            if "FROM ad_group" in query:
                return httpx.Response(200, json={"results": []})
            meta = ".name" in query
            rows = data["campaign"] if meta else data[key(query)]
            if meta:
                for row in rows:
                    row["campaign"]["name"] = "Brand A Owned Campaign"
            return httpx.Response(200, json={"results": rows})
        assert req.method == "GET" and req.url.host == "graph.facebook.com"
        if "name" in req.url.params.get("fields", "").split(","):
            rows = server.adsets if req.url.path.endswith("adsets") else server.campaigns
            for row in rows:
                row["name"] = "Brand B Owned Campaign"
            return httpx.Response(200, json={"data": rows})
        return server(req)

    monkeypatch.setattr(
        account_diagnostics, "diagnostic_transport", lambda: httpx.MockTransport(wire)
    )
    return calls


def bootstrap_reporting(db: Session, wid: int, scope: AccountScope) -> dict[str, str]:
    """Only declared input rows. No ready planning bundle, receipt or execution rows."""
    now = datetime.now(UTC)
    end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=1)
    account = db.get(AdvertisingAccount, scope.account_id)
    assert account is not None and account.workspace_id == wid
    native: Any
    if scope.platform == "google_ads":
        native = db.scalar(
            select(GoogleCustomerConnection).where(
                GoogleCustomerConnection.account_id == account.id
            )
        )
        assert native is not None
        native.encrypted_grant = GoogleVault().seal(wid, native.id, "synthetic-refresh")
        query = "google.v25.campaign-day.metrics-conversions.v1"
    else:
        native = db.scalar(select(MetaConnection).where(MetaConnection.account_id == account.id))
        assert native is not None
        native.encrypted_credentials = MetaVault(settings).seal(
            wid,
            native.external_account_id,
            dict(access_token=PRIVATE, expires_at=(now + timedelta(hours=1)).isoformat()),
        )
        native.covered_from = native.covered_through = start.date()
        native.conversion_action_type = "purchase"
        query = f"meta.{API_VERSION}.campaign-day.v1"
    native.last_sync_at = now
    campaign = Campaign(
        account_id=account.id,
        platform=account.platform,
        external_campaign_id="1" if scope.platform == "google_ads" else "5",
        name="Owned reporting campaign",
    )
    db.add(campaign)
    db.flush()
    db.add(
        DailyMetric(
            platform=account.platform,
            metric_date=start.date(),
            entity_type="campaign",
            entity_id=campaign.id,
            campaign_id=campaign.id,
            impressions=100,
            clicks=10,
            cost_micros=100_000_000,
            conversions=Decimal("2"),
            conversion_value_micros=200_000_000,
        )
    )
    db.flush()
    digest, rows = manifest(db, account, start.date(), start.date())
    completion = PerformanceCompletion(
        id=uuid4().hex,
        workspace_id=wid,
        account_id=account.id,
        platform=scope.platform,
        source_connection_ref=str(native.id),
        generation=native.generation,
        privacy_revision=workspace_export_revision(db, wid),
        starts_on=start.date(),
        ends_on=start.date(),
        currency="USD",
        time_zone="UTC",
        query_version=query,
        semantics="explicit_platform_event"
        if scope.platform == "meta_ads"
        else "provider_aggregate_unspecified",
        selected_event="purchase" if scope.platform == "meta_ads" else None,
        reporting_basis="provider_defaults_unspecified",
        completed_at=now,
        row_count=len(rows),
        manifest_digest=digest,
    )
    db.add(completion)
    db.flush()
    db.add(CurrentPerformance(account_id=account.id, workspace_id=wid, completion_id=completion.id))
    db.commit()
    return dict(starts_at=start.isoformat(), ends_at_exclusive=end.isoformat())
