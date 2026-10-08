"""Actual owned Meta 56-day MockHTTP import for API/browser acceptance, no ready bundles."""

import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

import pytest
from app.campaign_performance.models import CurrentPerformance, PerformanceCompletion
from app.campaign_performance.presence_contracts import ReportingSemanticsV1
from app.campaign_performance.presence_storage import read_presence
from app.campaign_performance.presence_summary import summarize_presence
from app.meta import client as meta_wire
from app.meta.client import MetaClient
from app.meta.models import MetaConnection
from app.meta.sync import MetaSyncService
from app.planning_documents.ports import GenerationTicket
from app.settings import Settings, settings
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_meta_connection import campaign, insight, page
from tests.test_planning_evidence_adapter import setup_evidence


@dataclass(frozen=True)
class ImportedWindowSource:
    # Ticket precedes import: use for goal/account IDs and customer inputs, never
    # as a freshly authorized generation ticket after the import's source change.
    ticket: GenerationTicket
    native_calls: list[str]
    starts_at: datetime
    ends_at: datetime
    imported: list[dict[str, Any]]
    payloads: list[dict[str, Any]]
    imported_requests: list[str]
    runtime: Settings
    header: ReportingSemanticsV1
    completion_id: str


def import_meta_window_source(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    state: str = "positive",
) -> ImportedWindowSource:
    assert state in {"positive", "zero", "missing", "sparse"}
    _, ticket, _, native_calls = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "meta_ads"
    )
    wid, aid = ticket.inputs.workspace_id, ticket.inputs.accounts[0].account_id
    now = datetime.now(UTC)
    end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=56)
    imported = []
    for offset in range(56):
        day = (start + timedelta(days=offset)).date().isoformat()
        positive = state == "positive" and offset == 49
        row = insight(
            account_id="123",
            campaign_id="5",
            date_start=day,
            date_stop=day,
            impressions="1000" if offset == 49 else "0",
            clicks="100" if offset == 49 else "0",
            spend="100" if offset == 49 else "0",
            actions=[{"action_type": "purchase", "value": "10" if positive else "0"}],
            action_values=[{"action_type": "purchase", "value": "200" if positive else "0"}],
        )
        if offset == 55 and state == "missing":
            del row["actions"]
        if offset != 55 or state != "sparse":
            imported.append(row)
    payloads = [page(campaign("5", "123")), page(), page(*imported)]
    imported_requests: list[str] = []

    class Opener:
        def open(self, request: Any, timeout: int) -> io.BytesIO:
            parsed = urlsplit(request.full_url)
            assert parsed.hostname == "graph.facebook.com"
            assert request.method == "GET" and timeout == 12
            imported_requests.append(parsed.path)
            return io.BytesIO(json.dumps(payloads.pop(0)).encode())

    monkeypatch.setattr(meta_wire, "build_opener", lambda *_: Opener())
    # Reuse the actual owned source's synthetic encryption key, not a forged source/context.
    runtime = Settings(
        _env_file=None,
        AD_ANALYZER_META_ENABLED=True,
        meta_client_id="100000000000001",
        meta_client_secret=settings.meta_client_secret,
        meta_token_encryption_key=settings.meta_token_encryption_key,
        meta_redirect_uri="https://example.test/dashboard/meta/callback",
    )
    with Session(customer_engine) as db:
        source = db.scalar(select(MetaConnection).where(MetaConnection.account_id == aid))
        assert source is not None and source.window_start is None and source.window_end is None
        current = db.get(CurrentPerformance, aid)
        assert current is not None
        old_completion = current.completion_id
        runner = MetaSyncService(db, runtime, MetaClient(runtime))
        for expected in ("syncing", "syncing", "complete"):
            result = runner.page(wid, now=now, manual=True)
            assert result["status"] == expected, result
        db.expire_all()
        current = db.get(CurrentPerformance, aid)
        assert current is not None and current.completion_id != old_completion
        completion = db.get(PerformanceCompletion, current.completion_id)
        assert completion is not None
        graph = read_presence(db, completion)
        assert graph is not None
        header, facts = graph
        assert len(facts) == (55 if state == "sparse" else 56)
        summary = summarize_presence(
            header, facts, campaign_id=facts[0].campaign_id, native_campaign_id="5"
        )
        assert summary.clicks.value == 100 and summary.spend_micros.value == 100_000_000
        assert summary.selected_conversions.value == (10 if state == "positive" else 0)
        assert summary.selected_zero_for_requested_window is (state == "zero")
        assert summary.selected_conversions.missing_days == (1 if state == "missing" else 0)
        assert summary.missing_calendar_days == (1 if state == "sparse" else 0)
    assert not payloads and len(imported_requests) == 3

    configure_paid_workspace(customer_engine, wid, monkeypatch)
    return ImportedWindowSource(
        ticket=ticket,
        native_calls=native_calls,
        starts_at=start,
        ends_at=end,
        imported=imported,
        payloads=payloads,
        imported_requests=imported_requests,
        runtime=runtime,
        header=header,
        completion_id=current.completion_id,
    )


def configure_paid_workspace(
    engine: Engine,
    workspace_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> Any:
    """Actual offline checkout/webhook reconciliation; no paid gate bypass or live money."""
    from app.billing.entitlements import paid_work
    from app.billing.service import checkout, reconcile
    from app.billing.webhooks import receive

    from tests import test_customer_billing as billing

    now = datetime.now(UTC)
    monkeypatch.setattr(billing, "NOW", now)
    fixture = billing.FixtureBilling()
    with Session(engine) as db:
        checkout(db, workspace_id, billing.POLICY, fixture, "https://inlet.example/settings", now)
        body = billing.payload("evt_window_active")
        assert receive(db, body, billing.signature(body, now), billing.SECRET, now)
        assert reconcile(db, workspace_id, "evt_window_active", billing.POLICY, fixture, now)
    monkeypatch.setattr(settings, "billing_required", True)
    monkeypatch.setattr(settings, "billing_price_id", billing.POLICY.price_id)
    monkeypatch.setattr(settings, "billing_max_accounts", 3)
    with Session(engine) as db:
        paid_work(db, workspace_id, datetime.now(UTC))
    return fixture
