"""Actual Meta read import through customer plan generation; no ready evidence bundle."""

import io
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

import pytest
from app.api import customer_planning_documents as api
from app.campaign_performance.models import CurrentPerformance, PerformanceCompletion
from app.campaign_performance.presence_storage import read_presence
from app.campaign_performance.presence_summary import summarize_presence
from app.meta import client as meta_wire
from app.meta.client import MetaClient
from app.meta.models import MetaConnection
from app.meta.sync import MetaSyncService
from app.publication.execution_models import ProviderExecutionAttempt, ProviderExecutionRun
from app.settings import Settings, settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.planning_legacy_policy_fixture import configure_legacy_v2_api
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_meta_connection import campaign, insight, page
from tests.test_planning_documents_api import create_body
from tests.test_planning_evidence_adapter import setup_evidence
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


@pytest.mark.parametrize("state", ["positive", "zero", "missing", "sparse"])
def test_actual_import_to_owned_plan_preserves_conversion_presence(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    state: str,
) -> None:
    configure_legacy_v2_api(monkeypatch)
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
        positive = state == "positive" and offset == 0
        row = insight(
            account_id="123",
            campaign_id="5",
            date_start=day,
            date_stop=day,
            impressions="1000" if offset == 0 else "0",
            clicks="100" if offset == 0 else "0",
            spend="100" if offset == 0 else "0",
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

    alice, _, _ = replicas
    alice.app.include_router(api.router)
    root = f"/api/customer/v1/workspaces/{wid}/planning/plans"
    body = create_body(ticket.inputs)
    body["inputs"]["reporting_window"] = dict(
        starts_at=start.isoformat(), ends_at_exclusive=end.isoformat()
    )
    created = alice.post(root, headers=headers(alice), json=body)
    assert created.status_code == 201, created.text
    url = root + "/" + created.json()["plan_id"]
    generated = alice.post(
        url + "/generate",
        headers=headers(alice),
        json=dict(expected_input_revision=1, expected_version=0, request_key="import-plan-first"),
    )
    assert generated.status_code == 200, generated.text
    document = generated.json()["document"]
    assert document["policy_version"] == "inlet.descriptive-review.v2"
    rationales = " ".join(action["rationale"] for action in document["actions"])
    assert "100 observed reported clicks" in rationales
    assert "100 USD observed reported spend" in rationales
    zero_statement = "observed zero selected conversions across the requested window"
    assert (zero_statement in rationales) is (state == "zero")
    if state == "positive":
        assert "10 observed provider-reported selected conversions" in rationales
        assert "spend without conversions" not in rationales.lower()
    elif state in {"missing", "sparse"}:
        assert "partial" in rationales or "unavailable" in rationales
    assert native_calls
    current_view = alice.get(url)
    assert current_view.status_code == 200 and current_view.json()["freshness"] == "current"
    exported = alice.get(url + "/export?version=1")
    assert exported.status_code == 200
    assert exported.json()["document_digest"] == generated.json()["document_digest"]
    if state == "zero":
        # A fresh actual import may withdraw an earlier observed-zero conclusion.
        # Numeric legacy rows remain zero; the new raw source omits selected counts.
        for row in imported:
            row.pop("actions", None)
        payloads.extend([page(campaign("5", "123")), page(), page(*imported)])
        corrected_at = datetime.now(UTC)
        with Session(customer_engine) as db:
            runner = MetaSyncService(db, runtime, MetaClient(runtime))
            for expected in ("syncing", "syncing", "complete"):
                result = runner.page(wid, now=corrected_at, manual=True)
                assert result["status"] == expected, result
        assert not payloads and len(imported_requests) == 6
        assert alice.get(url).json()["freshness"] != "current"
        history = alice.get(url + "/versions/1")
        assert history.status_code == 200 and history.json()["document"] == document
        successor = alice.post(
            url + "/generate",
            headers=headers(alice),
            json=dict(
                expected_input_revision=1, expected_version=1, request_key="import-correction"
            ),
        )
        assert successor.status_code == 200, successor.text
        assert successor.json()["version"] == 2
        next_document = successor.json()["document"]
        assert next_document["parent_digest"] == generated.json()["document_digest"]
        assert zero_statement not in " ".join(a["rationale"] for a in next_document["actions"])
        old_export = alice.get(url + "/export?version=1")
        assert old_export.status_code == 200
        assert old_export.json()["document_digest"] == generated.json()["document_digest"]
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderExecutionRun)) == 0
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
