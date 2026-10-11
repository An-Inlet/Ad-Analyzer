"""Explicit dated Q16 fixture; actual services/HTTP, no execution or ready-made plans."""

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
import pytest
from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount
from app.api import customer_goals, customer_planning_documents
from app.campaign_review import service as media
from app.campaign_review.storage import LocalMediaStore
from app.collectors import account_diagnostics
from app.commerce.models import CommerceStore
from app.commerce.sync import CommerceSyncService
from app.customers.models import CustomerMembership
from app.google_connections.models import GoogleCustomerConnection
from app.google_connections.security import Vault as GoogleVault
from app.settings import Settings, settings
from app.shopify.service import ConnectionService
from app.workspaces.models import Workspace, WorkspaceIntegration
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.q16_clock_feasibility_probe import NOV3, NOV4, issue_at, paid
from tests.test_commerce_measurement import FakeMeasurement, agreement, source
from tests.test_customer_identity import login
from tests.test_customer_optimization_api import headers
from tests.test_google_native_inventory import key, payloads

IMAGE = Path(__file__).parent / "fixtures/q16/synthetic-mug.png"


@dataclass(frozen=True)
class Q16Ids:
    workspace_id: int
    goal_id: str
    goal_revision: int
    confirmation_id: str
    store_id: str
    account_id: int
    media_id: str
    media_sha256: str
    plan_id: str
    version: int
    document_digest: str
    create_request_key: str
    generate_request_key: str


@dataclass(frozen=True)
class Q16Basis:
    workspace_id: int
    goal_id: str
    goal_revision: int
    confirmation_id: str
    store_id: str
    account_id: int
    media_id: str
    media_sha256: str
    body: dict[str, Any]


class NewYorkMeasurement(FakeMeasurement):
    def shop(self, shop: str, token: str) -> dict[str, Any]:
        result = super().shop(shop, token)
        result["shop"].update(id="gid://shopify/Shop/123", ianaTimezone="America/New_York")
        return result


def native_account(
    engine: Engine,
    wid: int,
    patch: pytest.MonkeyPatch,
    calls: list[str],
) -> int:
    patch.setattr(
        settings, "google_customer_encryption_key", SecretStr(Fernet.generate_key().decode())
    )
    patch.setattr(settings, "google_customer_client_id", "synthetic-client")
    patch.setattr(settings, "google_customer_client_secret", SecretStr("synthetic-secret"))
    patch.setattr(settings, "customer_native_diagnostics_enabled", True)
    with Session(engine) as db:
        integration = WorkspaceIntegration(
            workspace_id=wid,
            integration_key="q16-google",
            provider="google_ads",
            display_name="Q16 Google",
            status="active",
            configuration={},
        )
        db.add(integration)
        db.flush()
        account = AdvertisingAccount(
            workspace_id=wid,
            connection_id=integration.id,
            platform=AdvertisingPlatform("google_ads"),
            external_account_id="1234567890",
            name="Q16 Google",
            currency_code="USD",
            time_zone="America/New_York",
        )
        db.add(account)
        db.flush()
        sid = uuid4().hex
        db.add(
            GoogleCustomerConnection(
                id=sid,
                workspace_id=wid,
                integration_id=integration.id,
                account_id=account.id,
                external_account_id="1234567890",
                encrypted_grant=GoogleVault().seal(wid, sid, "synthetic-refresh"),
                backfill_through=date(2026, 9, 1),
                history_floor=date(2026, 8, 1),
                window_start=date(2026, 8, 1),
                window_end=date(2026, 9, 30),
            )
        )
        db.commit()
        aid = account.id

    def wire(req: httpx.Request) -> httpx.Response:
        calls.append(str(req.url))
        if req.url.host == "oauth2.googleapis.com":
            return httpx.Response(
                200,
                json=dict(
                    access_token="synthetic-google-access", token_type="Bearer", expires_in=3600
                ),
            )
        assert req.url.host == "googleads.googleapis.com" and ":mutate" not in req.url.path
        query = json.loads(req.content)["query"]
        data = payloads()
        data["campaign"][0]["campaign"]["name"] = "Mug Campaign"
        if "FROM ad_group" in query:
            rows = [
                {
                    "adGroup": dict(
                        id="7",
                        resourceName="customers/1234567890/adGroups/7",
                        campaign="customers/1234567890/campaigns/1",
                        name="Mug Ad Group",
                        status="ENABLED",
                        type="SEARCH_STANDARD",
                    )
                }
            ]
        else:
            rows = data["campaign"] if ".name" in query else data[key(query)]
        return httpx.Response(200, json={"results": rows})

    patch.setattr(account_diagnostics, "diagnostic_transport", lambda: httpx.MockTransport(wire))
    return aid


def prepare_q16_basis(
    engine: Engine,
    config: Settings,
    replicas: Any,
    patch: pytest.MonkeyPatch,
    artifacts: Path,
    *,
    branch: Literal["privacy", "progress"],
    native_calls: list[str],
    generation_stage: Literal["nov3", "october"] = "nov3",
) -> Q16Basis:
    now = datetime.now(UTC)
    assert now < NOV3 and now.year == 2026 and now.month == 10
    alice, _, provider = replicas
    actor = login(alice, "q16-owner:initial")
    config.shopify_measurement_enabled = True
    with Session(engine) as db:
        workspace = Workspace(slug="q16-" + branch, name="Q16", client_name="Q16", status="active")
        db.add(workspace)
        db.flush()
        wid = workspace.id
        db.add(CustomerMembership(user_id=actor, workspace_id=wid, role="owner"))
        db.commit()
        client = NewYorkMeasurement(config, [([source(updated=now - timedelta(seconds=1))], None)])
        client.facts = [
            agreement(
                gross="8000", tax="0", when=datetime.fromisoformat("2026-09-15T12:00:00-04:00")
            )
        ]
        connection = ConnectionService(db, config, client)
        auth = connection.begin(wid, "q16-store.myshopify.com", actor, now)
        nonce = parse_qs(urlsplit(auth).query)["state"][0]
        state = connection.pending(dict(state=nonce, shop="q16-store.myshopify.com"), actor, now)
        shop = connection.finish(state, "synthetic-code", "owner", now)
        assert shop.commerce_store_id
        store_id = shop.commerce_store_id
        store = db.get(CommerceStore, store_id)
        assert store and store.time_zone == "America/New_York" and store.last_sync_at is None
        result = CommerceSyncService(db, config, client).page(wid, now=now)
        assert result["status"] == "complete", result
    alice.app.include_router(customer_goals.router)
    alice.app.include_router(customer_planning_documents.router)
    goal_root = f"/api/customer/v1/workspaces/{wid}/goals"
    basis = dict(currency="USD", time_zone="America/New_York", time_basis="calendar_month")
    definition = dict(
        metric="shopify_merchandise_net_sales_v1",
        store_id=store_id,
        target_micros=12_000_000_000,
        target_window=dict(**basis, start="2026-11-01", end="2026-12-01"),
        baseline_window=dict(**basis, start="2026-09-01", end="2026-10-01"),
        deadline="2026-11-30",
        budget_micros=1_000_000_000,
        budget_start="2026-11-01",
        budget_end="2026-12-01",
        aggressiveness="balanced",
    )
    created = alice.post(
        goal_root,
        headers={**headers(alice), "Idempotency-Key": "q16-goal-create"},
        json=dict(definition=definition),
    )
    assert created.status_code == 201, created.text
    gid, revision = created.json()["id"], created.json()["revision"]
    preview = alice.post(
        goal_root + f"/{gid}/preview", headers=headers(alice), json=dict(expected_revision=revision)
    )
    assert preview.status_code == 200, preview.text
    confirmation = preview.json()["preview_id"]
    confirmed = alice.post(
        goal_root + f"/{gid}/confirm",
        headers=headers(alice),
        json=dict(
            expected_revision=revision, preview_id=confirmation, idempotency_key="q16-goal-confirm"
        ),
    )
    assert confirmed.status_code == 200, confirmed.text
    generation_at = NOV3 if generation_stage == "nov3" else datetime.now(UTC)
    aid = native_account(engine, wid, patch, native_calls)
    paid(engine, wid, generation_at, patch)
    with Session(engine) as db:
        if generation_stage == "nov3":
            client = NewYorkMeasurement(config, [([], None)])
            result = CommerceSyncService(db, config, client).page(wid, now=NOV3)
            assert result["status"] == "complete", result
        asset = media.upload(
            db, wid, actor, IMAGE.read_bytes(), LocalMediaStore(artifacts), generation_at
        )
        db.commit()
        media_id, image_digest = asset.id, asset.sha256
    if generation_stage == "nov3":
        issue_at(alice, provider, "q16-owner", NOV3)
    patch.setattr(
        customer_planning_documents,
        "utc_now",
        (lambda: NOV3) if generation_stage == "nov3" else (lambda: datetime.now(UTC)),
    )
    create_key = "q16-plan-create"
    body = dict(
        request_key=create_key,
        inputs=dict(
            goal_id=gid,
            goal_revision=revision,
            account_ids=[aid],
            reporting_window=dict(
                starts_at="2026-09-01T00:00:00-04:00", ends_at_exclusive="2026-10-01T00:00:00-04:00"
            ),
            comparison_window=dict(
                starts_at="2026-08-01T00:00:00-04:00", ends_at_exclusive="2026-09-01T00:00:00-04:00"
            ),
            milestone="Reach $12,000 November merchandise net sales",
            product_offer=(
                "Reusable travel mug, $25 list price. One owned synthetic product image: "
                f"media {media_id}, SHA256 {image_digest}. "
                "No approved health claims or testimonials."
            ),
            constraints=[],
            assumptions=[],
            exclusions=[],
            fixed_allocations=[],
            scenario_intents=[],
            maximum_creative_assets=1,
        ),
    )
    return Q16Basis(wid, gid, revision, confirmation, store_id, aid, media_id, image_digest, body)


def prepare_q16_case(
    engine: Engine,
    config: Settings,
    replicas: Any,
    patch: pytest.MonkeyPatch,
    artifacts: Path,
    *,
    branch: Literal["privacy", "progress"],
    native_calls: list[str],
    generation_stage: Literal["nov3", "october"] = "nov3",
) -> Q16Ids:
    basis = prepare_q16_basis(
        engine,
        config,
        replicas,
        patch,
        artifacts,
        branch=branch,
        native_calls=native_calls,
        generation_stage=generation_stage,
    )
    alice, _, _ = replicas
    wid, gid, revision = basis.workspace_id, basis.goal_id, basis.goal_revision
    confirmation, store_id, aid = basis.confirmation_id, basis.store_id, basis.account_id
    media_id, image_digest = basis.media_id, basis.media_sha256
    body = basis.body
    root = f"/api/customer/v1/workspaces/{wid}/planning/plans"
    create_key, generate_key = "q16-plan-create", "q16-plan-generate"
    planned = alice.post(root, headers=headers(alice), json=body)
    assert planned.status_code == 201, planned.text
    pid = planned.json()["plan_id"]
    generated = alice.post(
        root + f"/{pid}/generate",
        headers=headers(alice),
        json=dict(expected_input_revision=1, expected_version=0, request_key=generate_key),
    )
    assert generated.status_code == 200, generated.text
    return Q16Ids(
        wid,
        gid,
        revision,
        confirmation,
        store_id,
        aid,
        media_id,
        image_digest,
        pid,
        1,
        generated.json()["document_digest"],
        create_key,
        generate_key,
    )


def import_progress_stage(
    engine: Engine,
    config: Settings,
    ids: Q16Ids,
    *,
    stage: Literal["initial_day", "later_day", "refund_correction"],
) -> datetime:
    if stage == "initial_day":
        with Session(engine) as db:
            client = NewYorkMeasurement(config, [([], None)])
            result = CommerceSyncService(db, config, client).page(ids.workspace_id, now=NOV3)
            assert result["status"] == "complete", result
        return NOV3
    now = (
        NOV4
        if stage == "later_day"
        else NOV4 + timedelta(minutes=config.shopify_sync_interval_minutes + 1)
    )
    order = source(2, updated=now - timedelta(seconds=1))
    order["createdAt"] = (NOV3 + timedelta(hours=10)).isoformat()
    client = NewYorkMeasurement(config, [([order], None)])
    client.facts = [agreement(2, "25", "0", when=NOV3 + timedelta(hours=10))]
    if stage == "refund_correction":
        client.facts.append(agreement(3, "-5", "0", "RETURN", NOV3 + timedelta(hours=12)))
    with Session(engine) as db:
        result = CommerceSyncService(db, config, client).page(ids.workspace_id, now=now)
        assert result["status"] == "complete", result
    return now
