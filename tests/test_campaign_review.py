"""Offline media integrity and exact campaign review; no provider calls."""

import hashlib
import io
from collections.abc import Generator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from app.campaign_review import service as s
from app.campaign_review.contracts import RevisionInput
from app.campaign_review.models import CampaignRevision
from app.campaign_review.storage import LocalMediaStore, get_media_store
from app.google_connections.models import GoogleCustomerConnection
from app.mandates import service as mandates
from app.mandates.models import Mandate
from app.mandates.schemas import AccountScope
from app.settings import Settings
from app.workspaces.models import Workspace
from fastapi import HTTPException
from PIL import Image
from pydantic import ValidationError
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_action_plans import setup
from tests.test_shopify_sales import configuration as configuration


@pytest.fixture
def media_read_only_graph(customer_engine: Engine) -> Generator[None, None, None]:
    # Defer the fixture import: its source setup helpers also import this media module.
    from tests.tiktok_read_fixture import assert_no_advertising_authority

    assert_no_advertising_authority(customer_engine)
    yield
    assert_no_advertising_authority(customer_engine)


def definition(db: Session, mandate: Mandate, scope: AccountScope) -> RevisionInput:
    return RevisionInput(
        account=scope,
        mandate_id=mandate.id,
        mandate_revision=mandate.revision,
        currency="USD",
        budget_micros=60,
        starts_at=NOW,
        ends_at=NOW + timedelta(hours=1),
        content={
            "kind": "google_search_v1",
            "objective": "website_sales",
            "name": "Supplied campaign",
            "landing_page": "https://example.invalid/shop",
            "audience": {"countries": ["US"], "languages": ["en"]},
            "headlines": ["One", "Two", "Three"],
            "descriptions": ["Description one", "Description two"],
            "exact_keywords": ["supplied product"],
        },
    )


def png() -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (4, 4), "green").save(stream, "PNG")
    return stream.getvalue()


def test_exact_review_edit_and_stale_approval(
    customer_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    store = LocalMediaStore(tmp_path)
    with Session(customer_engine) as db:
        mandate, scope, _ = setup(db, configuration)
        body = definition(db, mandate, scope)
        first = s.revise(db, mandate.workspace_id, body, "owner", store, NOW)
        preview, artifact = s.preview(db, mandate.workspace_id, first.draft_id, store, NOW)
        assert artifact.offline_reviewable and not artifact.publication_eligible
        assert "tracking_conversion_binding_required" in artifact.publication_blockers
        assert preview.digest == artifact.fingerprint()
        with pytest.raises(HTTPException):
            s.approve(db, mandate.workspace_id, first.draft_id, 1, "a" * 64, "owner", store, NOW)
        approved = s.approve(
            db, mandate.workspace_id, first.draft_id, 1, first.digest, "owner", store, NOW
        )
        assert s.view(approved)["approved_for_offline_plan"]
        updated = body.model_copy(update={"budget_micros": 50})
        second = s.revise(db, mandate.workspace_id, updated, "owner", store, NOW, first.draft_id, 1)
        assert second.revision == 2 and second.digest != first.digest and second.approved_by is None
        historical = db.get(CampaignRevision, (first.draft_id, 1))
        assert historical is not None and historical.approved_by == "owner"
        with pytest.raises(HTTPException):
            s.approve(
                db, mandate.workspace_id, first.draft_id, 1, first.digest, "owner", store, NOW
            )
        with pytest.raises(HTTPException):
            s.revise(db, mandate.workspace_id, body, "owner", store, NOW, first.draft_id, 1)


@pytest.mark.parametrize("change", ["generation", "disconnect", "mandate", "paused", "expiry"])
def test_review_binding_rechecks(
    customer_engine: Engine, configuration: Settings, tmp_path: Path, change: str
) -> None:
    store = LocalMediaStore(tmp_path)
    with Session(customer_engine) as db:
        mandate, scope, _ = setup(db, configuration)
        first = s.revise(
            db, mandate.workspace_id, definition(db, mandate, scope), "owner", store, NOW
        )
        connection = db.scalar(select(GoogleCustomerConnection))
        assert connection is not None
        now = NOW
        if change == "generation":
            connection.generation += 1
        elif change == "disconnect":
            connection.status = "reconnect_required"
        elif change == "mandate":
            policy = mandates.policy(db, mandate)
            mandates.edit(db, mandate, mandate.revision, policy, "owner", NOW)
        elif change == "paused":
            mandate.paused = True
        else:
            now = NOW + timedelta(days=2)
        db.commit()
        with pytest.raises(HTTPException):
            s.approve(
                db, mandate.workspace_id, first.draft_id, 1, first.digest, "owner", store, now
            )
        assert first.approved_by is None


def test_scope_and_mandate_limits(
    customer_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    store = LocalMediaStore(tmp_path)
    with Session(customer_engine) as db:
        mandate, scope, _ = setup(db, configuration)
        body = definition(db, mandate, scope)
        row = s.revise(db, mandate.workspace_id, body, "owner", store, NOW)
        with pytest.raises(HTTPException) as caught:
            s.preview(db, mandate.workspace_id + 999, row.draft_id, store, NOW)
        assert caught.value.status_code == 404
        with pytest.raises(HTTPException):
            s.revise(
                db,
                mandate.workspace_id,
                body.model_copy(update={"budget_micros": 90}),
                "owner",
                store,
                NOW,
            )
        db.rollback()
        oversized = body.model_copy(deep=True)
        assert oversized.content.kind == "google_search_v1"
        oversized.content.headlines[0] = "x" * 31
        with pytest.raises(ValidationError):
            s.revise(db, mandate.workspace_id, oversized, "owner", store, NOW)


@pytest.mark.planning_boundary
@pytest.mark.usefixtures("media_read_only_graph")
def test_owned_media_and_integrity(
    customer_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    store = LocalMediaStore(tmp_path)
    with Session(customer_engine) as db:
        workspace = Workspace(slug="media", name="Media", client_name="Media")
        db.add(workspace)
        db.commit()
        wid = workspace.id
        row = s.upload(db, wid, "owner", png(), store, NOW)
        assert row.mime == "image/png" and row.width == 4
        assert s.upload(db, wid, "owner", png(), store, NOW).id == row.id
        assert s.download(db, wid, row.id, store)[1] == png()
        with pytest.raises(HTTPException) as caught:
            s.download(db, wid + 1, row.id, store)
        assert caught.value.status_code == 404
        path = tmp_path / str(wid) / row.sha256
        path.chmod(0o600)
        path.write_bytes(b"corruption")
        with pytest.raises(HTTPException) as caught:
            s.download(db, wid, row.id, store)
        assert caught.value.status_code == 503


@pytest.mark.parametrize(
    "data", [b"<svg></svg>", b"not an image", b"", b"x" * (8 * 1024 * 1024 + 1)]
)
@pytest.mark.planning_boundary
@pytest.mark.usefixtures("media_read_only_graph")
def test_reject_unvalidated_media(
    customer_engine: Engine, configuration: Settings, tmp_path: Path, data: bytes
) -> None:
    with Session(customer_engine) as db:
        workspace = Workspace(slug="media", name="Media", client_name="Media")
        db.add(workspace)
        db.commit()
        wid = workspace.id
        with pytest.raises(HTTPException):
            s.upload(db, wid, "owner", data, LocalMediaStore(tmp_path), NOW)


def test_private_immutable_store(tmp_path: Path) -> None:
    store = LocalMediaStore(tmp_path)
    data = png()
    sha = hashlib.sha256(data).hexdigest()
    store.put_if_absent(1, sha, len(data), [data])
    store.put_if_absent(1, sha, len(data), [data])
    with pytest.raises(ValueError):
        store.put_if_absent(1, sha, len(data), [b"x" * len(data)])
    assert store.read_exact(1, sha, len(data)) == data
    with pytest.raises(FileNotFoundError):
        store.read_exact(2, sha, len(data))
    with pytest.raises(ValueError):
        store.read_exact(1, "../escape", len(data))
    (tmp_path / "3").symlink_to(tmp_path / "1", target_is_directory=True)
    with pytest.raises(OSError):
        store.read_exact(3, sha, len(data))


def test_default_disabled() -> None:
    with pytest.raises(HTTPException) as caught:
        get_media_store()
    assert caught.value.status_code == 503


def test_unsupported_campaign_type(customer_engine: Engine, configuration: Settings) -> None:
    with Session(customer_engine) as db:
        mandate, scope, _ = setup(db, configuration)
        payload = definition(db, mandate, scope).model_dump(mode="json")
        payload["content"]["kind"] = "performance_max"
        with pytest.raises(ValidationError):
            RevisionInput.model_validate(payload)


def test_api_media_requires_current_session_csrf_and_owner(
    customer_engine: Engine, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app.api.customer import router as customer_router
    from app.api.customer_campaign_review import router
    from app.customers.access import CSRF_COOKIE
    from app.customers.identity import get_identity_provider
    from app.customers.models import CustomerMembership
    from app.database.session import get_db
    from app.settings import settings
    from app.workspaces.models import Workspace
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from tests.test_customer_identity import ORIGIN, FakeProvider, login

    monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)
    app = FastAPI()
    app.include_router(customer_router)
    app.include_router(router)

    def database() -> Generator[Session, None, None]:
        with Session(customer_engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_identity_provider] = lambda: FakeProvider()
    app.dependency_overrides[get_media_store] = lambda: LocalMediaStore(tmp_path)
    client = TestClient(app, base_url=ORIGIN)
    assert client.post("/api/customer/v1/workspaces/1/media", content=png()).status_code == 401
    actor = login(client, "media-owner")
    with Session(customer_engine) as db:
        workspace = Workspace(slug="media", name="Media", client_name="Media", status="active")
        db.add(workspace)
        db.flush()
        wid = workspace.id
        membership = CustomerMembership(user_id=actor, workspace_id=wid, role="viewer")
        db.add(membership)
        db.commit()
    url = f"/api/customer/v1/workspaces/{wid}/media"
    headers = {"Origin": ORIGIN, "X-CSRF-Token": client.cookies[CSRF_COOKIE]}
    assert client.post(url, content=png()).status_code == 403
    assert client.post(url, content=png(), headers=headers).status_code == 403
    with Session(customer_engine) as db:
        row = db.scalar(select(CustomerMembership).where(CustomerMembership.user_id == actor))
        assert row is not None
        row.role = "owner"
        db.commit()
    response = client.post(url, content=png(), headers=headers)
    assert response.status_code == 200, response.text
    media_id = response.json()["media_id"]
    result = client.get(url + "/" + media_id)
    assert result.status_code == 200 and result.content == png()
    assert result.headers["cache-control"] == "no-store"
    assert result.headers["x-content-type-options"] == "nosniff"
    assert client.get(f"/api/customer/v1/workspaces/{wid + 1}/media/{media_id}").status_code == 404


def test_entitlement_gate_on_review(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.settings import settings

    with Session(customer_engine) as db:
        mandate, scope, _ = setup(db, configuration)
        body = definition(db, mandate, scope)
        monkeypatch.setattr(settings, "billing_required", True)
        monkeypatch.setattr(settings, "billing_price_id", "")
        with pytest.raises(HTTPException) as caught:
            s.revise(db, mandate.workspace_id, body, "owner", LocalMediaStore(tmp_path), NOW)
        assert caught.value.status_code == 503


def test_image_review_binds_exact_media_and_meta_generation(
    customer_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    from app.ads.enums import AdvertisingPlatform
    from app.ads.models import AdvertisingAccount
    from app.meta.models import MetaConnection
    from app.workspaces.models import WorkspaceIntegration

    store = LocalMediaStore(tmp_path)
    with Session(customer_engine) as db:
        mandate, scope, _ = setup(db, configuration)
        integration = WorkspaceIntegration(
            workspace_id=mandate.workspace_id,
            integration_key="meta-review",
            provider="meta_ads",
            display_name="Meta",
            status="active",
            configuration={},
        )
        db.add(integration)
        db.flush()
        account = AdvertisingAccount(
            workspace_id=mandate.workspace_id,
            connection_id=integration.id,
            platform=AdvertisingPlatform.META_ADS,
            external_account_id="101",
            name="Meta",
            currency_code="USD",
            time_zone="UTC",
        )
        db.add(account)
        db.flush()
        connection = MetaConnection(
            workspace_id=mandate.workspace_id,
            workspace_integration_id=integration.id,
            account_id=account.id,
            external_account_id="101",
            encrypted_credentials="unopened-fixture",
        )
        db.add(connection)
        policy = mandates.policy(db, mandate)
        policy.accounts = [
            AccountScope(platform="meta_ads", connection_id=integration.id, account_id=account.id)
        ]
        mandates.edit(db, mandate, mandate.revision, policy, "owner", NOW)
        mandates.approve(db, mandate, mandate.revision, "owner", NOW)
        db.commit()
        media = s.upload(db, mandate.workspace_id, "owner", png(), store, NOW)
        body = RevisionInput(
            account=policy.accounts[0],
            mandate_id=mandate.id,
            mandate_revision=mandate.revision,
            currency="USD",
            budget_micros=60,
            starts_at=NOW,
            ends_at=NOW + timedelta(hours=1),
            content={
                "kind": "meta_website_sales_image_v1",
                "objective": "website_sales",
                "name": "Supplied image",
                "landing_page": "https://example.invalid/shop",
                "audience": {"countries": ["US"], "languages": ["en"]},
                "headline": "Shop",
                "text": "Supplied text",
                "call_to_action": "SHOP_NOW",
                "media": {"media_id": media.id, "sha256": media.sha256},
            },
        )
        row = s.revise(db, mandate.workspace_id, body, "owner", store, NOW)
        s.approve(db, mandate.workspace_id, row.draft_id, 1, row.digest, "owner", store, NOW)
        assert row.approved_by == "owner" and row.artifact["media"][0]["sha256"] == media.sha256
        # Token material rotation is not a customer-visible identity change.
        connection.encrypted_credentials = "rotated-unopened-fixture"
        db.commit()
        assert s.preview(db, mandate.workspace_id, row.draft_id, store, NOW)[0].digest == row.digest
        connection.generation += 1
        db.commit()
        with pytest.raises(HTTPException):
            s.preview(db, mandate.workspace_id, row.draft_id, store, NOW)


def test_concurrent_edit_has_one_winner(
    customer_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    if customer_engine.dialect.name != "postgresql":
        pytest.skip("row-lock race requires PostgreSQL")
    store = LocalMediaStore(tmp_path)
    with Session(customer_engine) as db:
        mandate, scope, _ = setup(db, configuration)
        body = definition(db, mandate, scope)
        first = s.revise(db, mandate.workspace_id, body, "owner", store, NOW)
        wid, draft_id = mandate.workspace_id, first.draft_id
    barrier = Barrier(2)

    def edit() -> int:
        with Session(customer_engine) as db:
            barrier.wait(timeout=10)
            try:
                s.revise(db, wid, body, "owner", store, NOW, draft_id, 1)
                return 200
            except HTTPException as exc:
                db.rollback()
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: edit(), range(2)))
    assert sorted(results) == [200, 409]
    with Session(customer_engine) as db:
        row, _ = s.preview(db, wid, draft_id, store, NOW)
        assert row.revision == 2 and row.approved_by is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("headlines", "x" * 31),
        ("headlines", "界" * 16),
        ("descriptions", "x" * 91),
        ("descriptions", "界" * 46),
        ("exact_keywords", "x" * 81),
        ("exact_keywords", "word " * 11),
    ],
)
def test_provider_copy_bounds(field: str, value: str) -> None:
    from app.campaign_review.contracts import GoogleSearch

    payload: dict[str, Any] = {
        "kind": "google_search_v1",
        "objective": "website_sales",
        "name": "Campaign",
        "landing_page": "https://example.invalid",
        "audience": {"countries": ["US"], "languages": ["en"]},
        "headlines": ["One", "Two", "Three"],
        "descriptions": ["First", "Second"],
        "exact_keywords": ["product"],
    }
    payload[field][0] = value
    with pytest.raises(ValidationError):
        GoogleSearch.model_validate(payload)
