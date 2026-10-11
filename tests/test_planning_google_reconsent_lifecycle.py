"""Fresh same-advertiser consent erases derived plans; it is not Q11 history preservation."""

import copy
import hashlib
import hmac
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from app.ads.models import AdvertisingAccount, Campaign, DailyMetric
from app.api import customer_google
from app.billing.entitlements import paid_work
from app.billing.models import WorkspaceBilling
from app.campaign_performance.presence_models import MetricPresenceRow, ReportingSemanticsRow
from app.campaign_performance.range_receipt_models import RangeReceiptRow
from app.campaign_performance.selected_models import (
    CurrentEventSelectionRow,
    EventSelectionRow,
    SelectedCaptureRow,
    SelectedFactRow,
)
from app.commerce.models import (
    CommerceEntry,
    CommerceMeasurementPublication,
    CommerceOrder,
    CommerceSnapshot,
    CommerceStore,
)
from app.commerce.sync import CommerceSyncService
from app.customers.access import SESSION_COOKIE
from app.customers.models import CustomerMembership
from app.goals import service as goals
from app.goals.models import Goal, GoalConfirmation, GoalRevision
from app.goals.schemas import ConfirmInput
from app.google_connections.contracts import get_transport
from app.google_connections.http import GoogleHTTPRead
from app.google_connections.models import GoogleCustomerConnection
from app.lifecycle.contracts import LifecycleInputV1, LifecycleScopeV1
from app.lifecycle.exports import Authority
from app.lifecycle.service import begin
from app.meta.models import MetaConnection
from app.meta.security import Vault as MetaVault
from app.planning_documents.catalog_receipt_models import (
    CatalogReceiptRow,
    CatalogReceiptSelectionRow,
    InputCatalogReceiptRow,
)
from app.planning_documents.documents import PlanVersion
from app.planning_documents.events import CustomerDecision
from app.planning_documents.models import (
    PlanDependencyRow,
    PlanEventRow,
    PlanInputRow,
    PlanRequestRow,
    PlanRow,
    PlanVersionRow,
)
from app.settings import Settings, settings
from app.shopify.security import utc
from app.workspaces.models import Workspace
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.creative_q05_fixture import _social_account
from tests.creative_runtime_fixture import configured
from tests.test_commerce_measurement import FakeMeasurement
from tests.test_commerce_measurement import source as commerce_source
from tests.test_creative_common_basis import financial_counts
from tests.test_creative_runtime_api import generation
from tests.test_customer_exports import build, unpack
from tests.test_customer_goals import seed
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary

PLANNING = (
    PlanRequestRow,
    PlanEventRow,
    InputCatalogReceiptRow,
    PlanDependencyRow,
    PlanVersionRow,
    PlanInputRow,
    PlanRow,
    CatalogReceiptSelectionRow,
    CatalogReceiptRow,
)
REPORTING = (
    RangeReceiptRow,
    EventSelectionRow,
    CurrentEventSelectionRow,
    SelectedCaptureRow,
    SelectedFactRow,
    ReportingSemanticsRow,
    MetricPresenceRow,
)


def _rows(db: Session, model: Any, wid: int) -> tuple[str, ...]:
    table = model.__table__
    if model is GoalConfirmation:
        condition = table.c.goal_id.in_(select(Goal.id).where(Goal.workspace_id == wid))
    elif model in (CommerceEntry, CommerceSnapshot):
        condition = table.c.store_id.in_(
            select(CommerceStore.id).where(CommerceStore.workspace_id == wid)
        )
    elif model is DailyMetric:
        condition = table.c.campaign_id.in_(
            select(Campaign.id).where(
                Campaign.account_id.in_(
                    select(AdvertisingAccount.id).where(AdvertisingAccount.workspace_id == wid)
                )
            )
        )
    elif model is Workspace:
        condition = table.c.id == wid
    elif model is Campaign:
        condition = table.c.account_id.in_(
            select(AdvertisingAccount.id).where(AdvertisingAccount.workspace_id == wid)
        )
    else:
        condition = table.c.workspace_id == wid
    return tuple(
        sorted(repr(dict(row)) for row in db.execute(select(table).where(condition)).mappings())
    )


def _snapshot(engine: Engine, wid: int, models: tuple[Any, ...]) -> dict[str, tuple[str, ...]]:
    with Session(engine) as db:
        return {model.__tablename__: _rows(db, model, wid) for model in models}


def _draft(
    alice: Any, root: str, original: dict[str, Any], aid: int, goal_id: str, revision: int, key: str
) -> tuple[str, dict[str, Any]]:
    body = copy.deepcopy(original)
    body["request_key"] = key
    body["inputs"].update(
        goal_id=goal_id,
        goal_revision=revision,
        account_ids=[aid],
        selected_reporting=[],
        exclusions=[],
        fixed_allocations=[],
        scenario_intents=[],
    )
    body["inputs"]["creative"]["media_selections"] = []
    response = alice.post(root, headers=headers(alice), json=body)
    assert response.status_code == 201, response.text
    saved = response.json()
    assert [a["account_id"] for a in saved["inputs"]["accounts"]] == [aid]
    url = root + "/" + saved["plan_id"]
    current = alice.get(url)
    assert current.status_code == 200 and current.json()["freshness"] == "not_generated"
    return url, saved


def test_actual_google_fresh_consent_erases_plans_not_protected_basis(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    f, root, body, native_calls, reader, store = configured(
        customer_engine, configuration, replicas, monkeypatch, tmp_path / "media"
    )
    alice = f.alice
    original_cookie = alice.cookies[SESSION_COOKIE]
    created = alice.post(root, headers=headers(alice), json=body)
    assert created.status_code == 201, created.text
    url = root + "/" + created.json()["plan_id"]
    generated = alice.post(url + "/generate", headers=headers(alice), json=generation())
    assert generated.status_code == 200, generated.text
    original = generated.json()
    document = PlanVersion.model_validate(original["document"])
    assert document.policy_version == "inlet.descriptive-review.v5"
    current = alice.get(url)
    assert current.status_code == 200 and current.json()["freshness"] == "current"
    view = current.json()
    action = view["document"]["actions"][0]
    decision = dict(
        expected_version=1,
        expected_event_sequence=0,
        document_digest=view["document_digest"],
        action_key=action["key"],
        action_digest=view["action_digests"][action["key"]],
        decision="accepted_for_manual_application",
        reason="Reviewed before fresh consent",
        supersedes_event_id=None,
        request_key="q11-accepted-before-consent",
    )
    accepted = alice.post(url + "/decisions", headers=headers(alice), json=decision)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["event_sequence"] == 1
    event = CustomerDecision.model_validate(accepted.json()["event"])
    event.assert_document(document)
    assert event.actor_id == f.actor
    assert event.decision == "accepted_for_manual_application"
    assert event.action_key == action["key"] and event.action_digest == decision["action_digest"]
    assert event.reason == decision["reason"] and event.supersedes_event_id is None
    exported = alice.get(url + "/export?version=1")
    events = alice.get(url + "/events")
    assert exported.status_code == events.status_code == 200
    assert exported.json()["document"] == original["document"]
    assert events.json()["items"] == [accepted.json()]
    for operation, key in (
        ("generate", generation()["request_key"]),
        ("decide", decision["request_key"]),
    ):
        assert alice.get(root + f"/requests/{operation}/{key}").status_code == 200

    # Genuine unrelated-account draft proves workspace-wide, not account-only erasure.
    meta_id = _social_account(customer_engine, f.wid, "meta_ads")
    same_url, _ = _draft(
        alice,
        root,
        body,
        meta_id,
        body["inputs"]["goal_id"],
        body["inputs"]["goal_revision"],
        "q11-same-workspace-meta",
    )
    # Separate owned control without a second configured() call or Vault/session reset.
    commerce_models = (CommerceStore, CommerceOrder, CommerceEntry, CommerceMeasurementPublication)
    primary_commerce = _snapshot(customer_engine, f.wid, commerce_models)
    with Session(customer_engine) as db:
        other_goal = seed(db, configuration, slug="q11-other")
        other_wid, other_goal_id = other_goal.workspace_id, other_goal.id
        db.add(
            CustomerMembership(
                user_id=f.actor, workspace_id=other_wid, role="owner", status="active"
            )
        )
        # The seed is historical. Acquire and publish fresh control-only evidence
        # through the real service before the normal-time goal baseline check.
        acquisition_started = datetime.now(UTC)
        measurement = FakeMeasurement(
            configuration, [([commerce_source(updated=acquisition_started)], None)]
        )
        imported = CommerceSyncService(db, configuration, measurement).page(other_wid)
        assert imported["status"] == "complete", imported
        assert len(measurement.requests) == 1 and measurement.pages == []
        control_store = db.scalar(
            select(CommerceStore).where(CommerceStore.workspace_id == other_wid)
        )
        publication = db.scalars(
            select(CommerceMeasurementPublication).where(
                CommerceMeasurementPublication.workspace_id == other_wid
            )
        ).one()
        assert control_store is not None and publication.store_id == control_store.id
        now = datetime.now(UTC)
        assert acquisition_started <= utc(publication.published_at) <= now
        assert utc(publication.source_window_end) == utc(publication.published_at)
        assert control_store.last_sync_at is not None
        assert utc(control_store.last_sync_at) == utc(publication.source_window_end)
        assert publication.completion_digest and publication.manifest_digest
        preview = goals.preview(db, other_goal, now)
        goals.confirm(
            db,
            other_goal,
            ConfirmInput(
                expected_revision=other_goal.revision,
                preview_id=preview.id,
                idempotency_key="q11-other-confirm",
            ),
            now,
            actor_id=f.actor,
        )
        db.commit()
        other_revision = other_goal.revision
        paid_work(
            db, other_wid, datetime.now(UTC)
        )  # Existing configured rollout gate, never overridden.
    assert _snapshot(customer_engine, f.wid, commerce_models) == primary_commerce
    other_id = _social_account(customer_engine, other_wid, "meta_ads", external_id="456")
    with Session(customer_engine) as db:
        for wid, aid, expected_external_id in (
            (f.wid, meta_id, "123"),
            (other_wid, other_id, "456"),
        ):
            owned_account = db.get(AdvertisingAccount, aid)
            owned_connection = db.scalars(
                select(MetaConnection).where(MetaConnection.account_id == aid)
            ).one()
            assert owned_account is not None
            assert owned_account.workspace_id == owned_connection.workspace_id == wid
            assert owned_account.id == owned_connection.account_id == aid
            assert owned_account.connection_id == owned_connection.workspace_integration_id
            assert owned_account.external_account_id == expected_external_id
            assert owned_connection.external_account_id == expected_external_id
            # Vault verifies the exact workspace/native identity AAD. Never print secrets.
            opened = MetaVault(settings).open(
                wid, expected_external_id, owned_connection.encrypted_credentials
            )
            has_token = bool(opened.get("access_token"))
            assert has_token, "Owned fixture credential unavailable"
            assert datetime.fromisoformat(opened["expires_at"]) > datetime.now(UTC)
    other_root = f"/api/customer/v1/workspaces/{other_wid}/planning/plans"
    other_url, other_saved = _draft(
        alice, other_root, body, other_id, other_goal_id, other_revision, "q11-other-workspace-meta"
    )

    monkeypatch.setattr(settings, "customer_export_enabled", True)
    with Session(customer_engine) as db:
        request = begin(
            db,
            reader.principal,
            f.provider,
            LifecycleInputV1(scope=LifecycleScopeV1(workspace_id=f.wid), operation="export"),
            "q11-before-reconsent-export",
            datetime.now(UTC),
        )
        db.commit()
        authority = Authority(customer_engine, reader.principal, f.provider, f.wid, request.id)
    authority.claim()
    archive, _ = build(customer_engine, authority, store)
    try:
        _, entries = unpack(archive)
        versions = [
            json.loads(line)
            for line in entries["data/planning_document_versions.jsonl"].splitlines()
        ]
        assert len(versions) == 1 and versions[0]["document"] == original["document"]
        archive_events = [
            json.loads(line) for line in entries["data/planning_document_events.jsonl"].splitlines()
        ]
        assert len(archive_events) == 1
        assert archive_events[0]["document"] == accepted.json()["event"]
        assert archive_events[0]["digest"] == event.digest()
        authority.check()
    finally:
        archive.close()  # build's SQL contexts and archive handle released before reconsent.

    protected_models = (
        Goal,
        GoalRevision,
        GoalConfirmation,
        CommerceStore,
        CommerceOrder,
        CommerceEntry,
        CommerceSnapshot,
        Campaign,
        DailyMetric,
    )
    protected = _snapshot(customer_engine, f.wid, protected_models)
    assert all(protected.values())
    control_models = (
        protected_models
        + PLANNING
        + REPORTING
        + (Workspace, CustomerMembership, WorkspaceBilling, AdvertisingAccount)
    )
    control = _snapshot(customer_engine, other_wid, control_models)
    for model in (
        Goal,
        GoalRevision,
        GoalConfirmation,
        CommerceEntry,
        PlanRow,
        PlanInputRow,
        PlanRequestRow,
        CustomerMembership,
    ):
        assert control[model.__tablename__]
    before_plans = _snapshot(customer_engine, f.wid, PLANNING)
    assert before_plans[PlanEventRow.__tablename__] and before_plans[PlanVersionRow.__tablename__]
    assert len(before_plans[PlanRow.__tablename__]) == 2
    before_reporting = _snapshot(customer_engine, f.wid, REPORTING)
    assert all(before_reporting.values())
    financial = financial_counts(customer_engine)
    assert financial == (0,) * 6  # No nonempty advertising-liability preservation claim.
    with Session(customer_engine) as db:
        source = db.get(GoogleCustomerConnection, f.source_id)
        account = db.get(AdvertisingAccount, f.aid)
        workspace = db.get(Workspace, f.wid)
        other_workspace = db.get(Workspace, other_wid)
        assert source and account and workspace and other_workspace
        source_identity = (
            source.id,
            source.account_id,
            source.integration_id,
            source.external_account_id,
        )
        generation_before, privacy_before = source.generation, workspace.export_privacy_revision
        other_privacy = other_workspace.export_privacy_revision
        external, currency, zone, name = (
            account.external_account_id,
            account.currency_code,
            account.time_zone,
            account.name,
        )
        original_grant = source.encrypted_grant
    calls_before = len(native_calls), len(f.calls)
    exchanges: list[str] = []
    oauth_client_id = settings.google_customer_client_id
    assert oauth_client_id

    def wire(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            assert request.method == "POST" and request.url.path == "/token"
            form = parse_qs(request.content.decode())
            client_matches = form.get("client_id") == [oauth_client_id]
            assert client_matches, "OAuth client binding mismatch"
            assert form["grant_type"] == ["authorization_code"]
            assert form["redirect_uri"] == [
                settings.customer_app_origin + "/api/customer/v1/google/callback"
            ]
            exchanges.append("authorization_code")
            return httpx.Response(
                200,
                json=dict(
                    access_token="q11-synthetic-access",
                    token_type="Bearer",
                    refresh_token="q11-distinct-synthetic-refresh",
                    expires_in=3600,
                ),
            )
        assert request.url.host == "googleads.googleapis.com"
        if request.method == "GET":
            assert request.url.path == "/v24/customers:listAccessibleCustomers"
            exchanges.append("accessible_accounts")
            return httpx.Response(200, json={"resourceNames": ["customers/" + external]})
        assert (
            request.method == "POST"
            and request.url.path == f"/v24/customers/{external}/googleAds:search"
        )
        assert json.loads(request.content) == dict(
            query=(
                "SELECT customer.id, customer.descriptive_name, customer.currency_code, "
                "customer.time_zone, customer.manager FROM customer LIMIT 1"
            ),
            pageToken="",
        )
        exchanges.append("customer_metadata")
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "customer": dict(
                            id=external,
                            manager=False,
                            descriptiveName=name,
                            currencyCode=currency,
                            timeZone=zone,
                        )
                    }
                ]
            },
        )

    transport = httpx.MockTransport(wire)
    oauth = GoogleHTTPRead(
        oauth_client_id,
        SecretStr("synthetic-secret"),
        SecretStr("synthetic-developer"),
        "v24",
        transport=transport,
    )
    alice.app.include_router(customer_google.router)
    alice.app.dependency_overrides[get_transport] = lambda: oauth
    google_root = f"/api/customer/v1/workspaces/{f.wid}/google"
    try:
        started = alice.post(google_root + "/authorize", headers=headers(alice))
        assert started.status_code == 200, started.text
        authorization_query = parse_qs(urlsplit(started.json()["authorization_url"]).query)
        client_matches = authorization_query.get("client_id") == [oauth_client_id]
        assert client_matches, "OAuth authorization client binding mismatch"
        state = authorization_query["state"][0]
        callback = alice.post(
            "/api/customer/v1/google/callback",
            headers=headers(alice),
            json=dict(state=state, code="q11-synthetic-code"),
        )
        assert callback.status_code == 200, callback.text
        assert [a["external_id"] for a in callback.json()["accounts"]] == [external]
        selection = dict(state=state, external_account_id=external)
        selected = alice.post(google_root + "/select", headers=headers(alice), json=selection)
        assert selected.status_code == 200, selected.text
        assert exchanges == ["authorization_code", "accessible_accounts", "customer_metadata"]
        assert (len(native_calls), len(f.calls)) == calls_before
        with Session(customer_engine) as db:
            source = db.get(GoogleCustomerConnection, f.source_id)
            workspace = db.get(Workspace, f.wid)
            assert source and workspace
            assert (
                source.id,
                source.account_id,
                source.integration_id,
                source.external_account_id,
            ) == source_identity
            assert source.generation == generation_before + 1
            privacy_after = workspace.export_privacy_revision
            assert privacy_after > privacy_before
            assert source.status == "connected" and source.cursor is None and source.staged == {}
            if source.encrypted_grant is None or source.encrypted_grant == original_grant:
                raise AssertionError("Fresh consent grant was not replaced")
        assert not any(_snapshot(customer_engine, f.wid, PLANNING + REPORTING).values())
        for old in (url, same_url):
            for suffix in ("", "/versions/1", "/events", "/export?version=1"):
                response = alice.get(old + suffix)
                assert response.status_code == 404 and response.json()["detail"] == "plan not found"
        rejected = alice.post(url + "/generate", headers=headers(alice), json=generation())
        assert rejected.status_code == 404 and rejected.json()["detail"] == "plan not found"
        for operation, key in (
            ("generate", generation()["request_key"]),
            ("decide", decision["request_key"]),
        ):
            response = alice.get(root + f"/requests/{operation}/{key}")
            assert (
                response.status_code == 404
                and response.json()["detail"] == "planning request not found"
            )
        with pytest.raises(HTTPException) as invalidated:
            authority.check()
        assert invalidated.value.status_code == 409
        assert invalidated.value.detail == "export source data was invalidated; build a new archive"
        replay = alice.post(google_root + "/select", headers=headers(alice), json=selection)
        assert replay.status_code == 200 and replay.json() == selected.json()
        assert len(exchanges) == 3 and (len(native_calls), len(f.calls)) == calls_before
        with Session(customer_engine) as db:
            source = db.get(GoogleCustomerConnection, f.source_id)
            workspace = db.get(Workspace, f.wid)
            other_workspace = db.get(Workspace, other_wid)
            assert source and workspace and other_workspace
            assert (
                source.generation == generation_before + 1
                and workspace.export_privacy_revision == privacy_after
            )
            assert other_workspace.export_privacy_revision == other_privacy
        assert not any(_snapshot(customer_engine, f.wid, PLANNING + REPORTING).values())
        assert _snapshot(customer_engine, f.wid, protected_models) == protected
        assert _snapshot(customer_engine, other_wid, control_models) == control
        other_current = alice.get(other_url)
        assert (
            other_current.status_code == 200
            and other_current.json()["freshness"] == "not_generated"
        )
        assert other_current.json()["inputs"] == other_saved["inputs"]
        assert financial_counts(customer_engine) == financial
        if not hmac.compare_digest(alice.cookies[SESSION_COOKIE], original_cookie):
            raise AssertionError("Original customer session changed")
    finally:
        transport.close()
        alice.app.dependency_overrides.pop(get_transport, None)
    artifacts = {
        "original-version": original,
        "original-export": exported.json(),
        "original-events": events.json(),
        "outcome": dict(
            erased_versions=1,
            erased_decisions=1,
            erased_plans=2,
            control_draft_preserved=True,
            fresh_consent_calls=exchanges,
            old_graph_resurrected=False,
            nonempty_ad_liability_qualification=False,
            q11_preserved_history_reconnect=False,
        ),
    }
    manifest = {}
    for key, value in artifacts.items():
        path = tmp_path / (key + ".json")
        path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
        manifest[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    (tmp_path / "artifacts.json").write_text(json.dumps(manifest, indent=2) + "\n")
