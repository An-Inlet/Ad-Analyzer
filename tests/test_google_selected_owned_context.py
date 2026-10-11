"""Actual owned SQL/Vault/OAuth read composition; synthetic HTTP, no live provider."""

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from app.ads.models import AdvertisingAccount, DailyMetric
from app.automation.catalog import AutomationControlKey
from app.automation.service import AutomationControlService
from app.campaign_performance.models import CurrentPerformance, PerformanceCompletion
from app.campaign_performance.presence_contracts import AttributionBasisV1
from app.campaign_performance.selected_contracts import (
    AggregateDependencyV1,
    CustomerEventSelectionV1,
    SelectedCaptureRequestV1,
    selection_digest,
)
from app.campaign_performance.selected_storage import store_selection
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.google_connections import service
from app.google_connections.http import GoogleHTTPRead
from app.google_connections.models import GoogleCustomerConnection
from app.google_connections.security import Vault
from app.google_connections.selected_catalog import GoogleReportingCatalogHTTP
from app.google_connections.selected_http import GoogleSelectedHTTPRead
from app.google_connections.selected_owned_context import OwnedGoogleReportingContext
from app.google_connections.selected_presence import PRODUCER, query_profile_digest
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_customer_connections import (
    FixtureTransport,
    connect,
    setup,
)
from tests.test_google_customer_connections import (
    configured as configured,
)


@pytest.fixture(autouse=True)
def enforce_fk(customer_engine: Engine) -> None:
    if customer_engine.dialect.name == "sqlite":
        with customer_engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
            connection.commit()


class Fixture:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.now = datetime.now(UTC)
        self.clock = self.now
        self.hook: Callable[[], None] = lambda: None
        self.calls: list[str] = []
        self.identity = FakeProvider()
        self.identity.issuer = "fixture"
        with Session(engine) as db:
            self.wid, self.sid = setup(db, "reporting-owner")
            session = db.get(CustomerSession, self.sid)
            assert session
            session.expires_at = int(self.now.timestamp()) + 3600
            user = db.get(CustomerUser, session.user_id)
            assert user
            db.add(
                CustomerMembership(
                    workspace_id=self.wid, user_id=user.id, status="active", role="owner"
                )
            )
            db.commit()
            source, _ = connect(db, self.wid, self.sid, FixtureTransport())
            self.aid, self.source_id = source.account_id, source.id
            self.day = source.window_start
            self.end_day = source.window_end
            self.actor = user.id
            db.refresh(user)
            db.refresh(session)
            self.principal = CustomerPrincipal(user, session)
            db.expunge_all()
        self.transport = httpx.MockTransport(self.handle)
        self.oauth = GoogleHTTPRead(
            "fixture-client",
            SecretStr("fixture-secret"),
            SecretStr("fixture-developer"),
            "v24",
            transport=self.transport,
        )

    def handle(self, req: httpx.Request) -> httpx.Response:
        self.calls.append(req.url.host or "")
        if req.url.host == "oauth2.googleapis.com":
            assert b"synthetic-fixture-value" in req.content
            self.hook()
            return httpx.Response(
                200,
                json={"access_token": "fixture-access", "token_type": "Bearer", "expires_in": 30},
            )
        query = json.loads(req.content)["query"]
        if "FROM customer" in query:
            data = {
                "customer": {
                    "id": "1234567890",
                    "resourceName": "customers/1234567890",
                    "currencyCode": "USD",
                    "timeZone": "UTC",
                }
            }
        elif "FROM conversion_action" in query:
            action = {
                "resourceName": "customers/1234567890/conversionActions/123",
                "ownerCustomer": "customers/1234567890",
            }
            if "conversion_action.name" in query:
                action.update(
                    name="Observed lead", status="ENABLED", category="CONTACT", type="UPLOAD_CLICKS"
                )
            data = {"conversionAction": action}
        elif "metrics." not in query:
            data = {
                "campaign": {
                    "id": "1",
                    "name": "Observed campaign",
                    "status": "PAUSED",
                    "advertisingChannelType": "SEARCH",
                }
            }
        else:
            data = {
                "campaign": {"id": "1", "resourceName": "customers/1234567890/campaigns/1"},
                "segments": {"date": self.day.isoformat()},
                "metrics": {
                    "impressions": "1000",
                    "clicks": "100",
                    "costMicros": "100000000",
                    "conversions": "10",
                    "conversionsValue": "0",
                },
            }
            if "segments.conversion_action" in query:
                data["segments"]["conversionAction"] = "customers/1234567890/conversionActions/123"
        rows = [data]
        if "metrics." in query and "segments.conversion_action" not in query:
            second = json.loads(json.dumps(data))
            second["segments"]["date"] = self.end_day.isoformat()
            rows.append(second)
        return httpx.Response(200, json={"results": rows})

    def resolver(self) -> OwnedGoogleReportingContext:
        return OwnedGoogleReportingContext(
            lambda: Session(self.engine),
            self.principal,
            self.identity,
            self.wid,
            self.aid,
            self.oauth,
            Vault(),
            lambda: self.clock,
        )

    def selected(self) -> SelectedCaptureRequestV1:
        with Session(self.engine) as db:
            source = db.get(GoogleCustomerConnection, self.source_id)
            assert source
            for _ in range(2):
                service.tick(db, self.wid, self.source_id, source.generation, self.oauth, self.now)
            current = db.get(CurrentPerformance, self.aid)
            assert current
            completion = db.get(PerformanceCompletion, current.completion_id)
            assert completion
            scope = self.resolver().catalog_request().scope
            selection = CustomerEventSelectionV1(
                selection_id=uuid4().hex,
                scope=scope,
                confirmed_by_customer_id=self.actor,
                confirmed_at=self.now,
                event_namespace="google_conversion_action",
                native_event_owner_id="1234567890",
                native_event_id="customers/1234567890/conversionActions/123",
                metric_family="conversions",
                api_version="v24",
                query_profile_digest=query_profile_digest("conversions"),
            )
            store_selection(db, selection, None, None)
            db.commit()
            return SelectedCaptureRequestV1(
                capture_id=uuid4().hex,
                aggregate=AggregateDependencyV1(
                    completion_id=completion.id,
                    manifest_digest=completion.manifest_digest,
                    scope=scope,
                    starts_on=completion.starts_on,
                    ends_on=completion.ends_on,
                ),
                selection=selection,
                selection_digest=selection_digest(selection),
                requested_starts_on=self.day,
                requested_ends_on=self.day,
                started_at=self.now,
                producer_contract=PRODUCER,
                query_profile_digest=selection.query_profile_digest,
                attribution=AttributionBasisV1(
                    click_window_days=None,
                    view_window_days=None,
                    report_time_basis="unknown",
                    provenance="provider_default_unknown",
                    producer_contract=PRODUCER,
                ),
            )


def test_actual_owned_catalog_and_selected_http(customer_engine: Engine, configured: None) -> None:
    f = Fixture(customer_engine)
    resolver = f.resolver()
    request = resolver.catalog_request()
    catalog = GoogleReportingCatalogHTTP(
        resolver.catalog_context,
        resolver.revalidate_catalog,
        transport=f.transport,
        clock=lambda: f.clock,
    )(request)
    assert len(catalog.options) == 2
    ctx = resolver.catalog_context(request)
    assert ctx.expires_at == f.now + timedelta(seconds=30)
    assert "fixture-access" not in ctx.model_dump_json() + repr(ctx)
    selected = f.selected()
    resolver = f.resolver()
    with Session(customer_engine) as db:
        from app.ads.models import Campaign

        campaign = db.scalar(select(Campaign).where(Campaign.account_id == f.aid))
        assert campaign
        mapping = {"1": campaign.id}
    page = GoogleSelectedHTTPRead(
        resolver.selected_context,
        resolver.revalidate_selected,
        transport=f.transport,
        clock=lambda: f.clock,
    )(selected, mapping)
    assert page.facts[0].selected_conversions.value == 10


@pytest.mark.parametrize(
    "change",
    ["session", "identity", "role", "generation", "currency", "grant", "login", "pause", "expiry"],
)
def test_oauth_io_races_fail_closed(customer_engine: Engine, configured: None, change: str) -> None:
    f = Fixture(customer_engine)
    resolver = f.resolver()
    req = resolver.catalog_request()

    def mutate() -> None:
        with Session(customer_engine) as db:
            source = db.get(GoogleCustomerConnection, f.source_id)
            user = db.get(CustomerUser, f.actor)
            session = db.get(CustomerSession, f.sid)
            member = db.get(CustomerMembership, (f.actor, f.wid))
            account = db.get(AdvertisingAccount, f.aid)
            assert source and user and session and member and account
            if change == "session":
                session.revoked_at = 1
            if change == "identity":
                user.subject = "changed"
            if change == "role":
                member.role = "viewer"
            if change == "generation":
                source.generation += 1
            if change == "currency":
                account.currency_code = "EUR"
            if change == "grant":
                source.encrypted_grant = Vault().seal(f.wid, source.id, "changed")
            if change == "login":
                source.login_customer_id = "9999999999"
            if change == "pause":
                AutomationControlService(db).set_master(
                    AutomationControlKey.ALL_DATA_SYNCS, enabled=False, actor="fixture"
                )
            if change == "expiry":
                f.clock += timedelta(seconds=31)
            db.commit()

    f.hook = mutate
    with pytest.raises((HTTPException, ValueError)):
        resolver.catalog_context(req)
    assert f.calls == ["oauth2.googleapis.com"]


def test_capture_manifest_change_during_refresh(customer_engine: Engine, configured: None) -> None:
    f = Fixture(customer_engine)
    request = f.selected()
    resolver = f.resolver()

    def mutate() -> None:
        with Session(customer_engine) as db:
            row = db.scalar(
                select(DailyMetric).where(DailyMetric.metric_date != request.requested_starts_on)
            )
            assert row
            row.clicks += 1
            db.commit()

    f.hook = mutate
    with pytest.raises((HTTPException, ValueError)):
        resolver.selected_context(request)


def test_incompatible_configuration_and_original_scope(
    customer_engine: Engine, configured: None
) -> None:
    f = Fixture(customer_engine)
    f.oauth.version = "v25"
    with pytest.raises(HTTPException):
        f.resolver()
    assert not f.calls
    f.oauth.version = "v24"
    resolver = f.resolver()
    req = resolver.catalog_request()
    with pytest.raises(HTTPException):
        resolver.catalog_context(req.model_copy(update={"actor_id": "a" * 32}))
    with Session(customer_engine) as db:
        session = db.get(CustomerSession, f.sid)
        assert session
        session.authenticated_at += 1
        db.commit()
    with pytest.raises(HTTPException):
        resolver.revalidate_catalog(req)
    assert not f.calls


@pytest.mark.parametrize("change", ["privacy", "selection", "pointer"])
def test_selected_dependency_changes_after_oauth(
    customer_engine: Engine, configured: None, change: str
) -> None:
    from app.campaign_performance.selected_storage import invalidate_selected_account
    from app.lifecycle.privacy import bump_workspace_export_revision

    f = Fixture(customer_engine)
    request = f.selected()
    resolver = f.resolver()

    def mutate() -> None:
        with Session(customer_engine) as db:
            if change == "privacy":
                bump_workspace_export_revision(db, f.wid)
            elif change == "selection":
                invalidate_selected_account(db, f.wid, f.aid)
            else:
                pointer = db.get(CurrentPerformance, f.aid)
                assert pointer
                db.delete(pointer)
            db.commit()

    f.hook = mutate
    with pytest.raises((HTTPException, ValueError)):
        resolver.selected_context(request)


def test_foreign_account_paid_gate_and_elapsed_authorization(
    customer_engine: Engine, configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.settings import settings

    f = Fixture(customer_engine)
    foreign = OwnedGoogleReportingContext(
        lambda: Session(customer_engine),
        f.principal,
        f.identity,
        f.wid,
        f.aid + 999,
        f.oauth,
        Vault(),
        lambda: f.clock,
    )
    with pytest.raises(HTTPException):
        foreign.catalog_request()
    monkeypatch.setattr(settings, "billing_required", True)
    with pytest.raises(HTTPException):
        f.resolver().catalog_request()
    monkeypatch.setattr(settings, "billing_required", False)
    resolver = f.resolver()
    req = resolver.catalog_request()

    def delay(subject: str, authenticated_at: int) -> None:
        f.clock += timedelta(seconds=61)

    monkeypatch.setattr(f.identity, "check_active", delay)
    with pytest.raises(HTTPException):
        resolver.catalog_context(req)
    assert not f.calls


def test_capture_outer_deadline_cannot_be_extended(
    customer_engine: Engine, configured: None
) -> None:
    f = Fixture(customer_engine)
    request = f.selected()
    f.clock += timedelta(seconds=61)
    resolver = f.resolver()
    calls_before = len(f.calls)
    with pytest.raises(HTTPException):
        resolver.selected_context(request)
    assert len(f.calls) == calls_before
