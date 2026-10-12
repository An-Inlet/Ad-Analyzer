"""Configured actual app creative/media flows; no planner or media dependency overrides."""

import json
from pathlib import Path
from typing import Any

import pytest
from app.api import customer_planning_documents as api
from app.campaign_review.storage import LocalMediaStore, get_media_store
from app.lifecycle.privacy import bump_workspace_export_revision
from app.main import app
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import (
    PlanDependencyRow,
    PlanEventRow,
    PlanInputRow,
    PlanRequestRow,
    PlanRow,
    PlanVersionRow,
)
from app.planning_documents.runtime_media import ConfiguredPlanningMedia
from app.planning_documents.service import PlanningDocumentService
from app.settings import Settings, settings
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests import test_creative_planning_browser as browser
from tests.creative_common_basis_fixture import Platform, prepare_creative_common_basis
from tests.test_creative_runtime_api import generation
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_planning_runtime_composition import configure
from tests.test_shopify_sales import configuration as configuration


def media_config(patch: pytest.MonkeyPatch, root: Path, mode: str = "local_dev") -> None:
    patch.setenv("AD_ANALYZER_MEDIA_STORAGE_MODE", mode)
    patch.setenv("AD_ANALYZER_MEDIA_LOCAL_DIRECTORY", str(root))
    parsed = configure(patch, "v5")
    patch.setattr(settings, "media_storage_mode", parsed.media_storage_mode)
    patch.setattr(settings, "media_local_directory", parsed.media_local_directory)


def test_lazy_read_only_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.planning_documents import runtime_media

    calls = []

    def unavailable() -> Any:
        calls.append(True)
        raise HTTPException(503, "private media storage unavailable")

    monkeypatch.setattr(runtime_media, "get_media_store", unavailable)
    store = ConfiguredPlanningMedia()
    assert not calls
    with pytest.raises(ValueError, match="read-only"):
        store.put_if_absent(1, "a" * 64, 1, [b"x"])
    assert not calls
    with pytest.raises(HTTPException) as caught:
        store.read_exact(1, "a" * 64, 1)
    assert caught.value.status_code == 503 and calls == [True]


@pytest.fixture
def assembled(
    customer_engine: Engine, configuration: Settings, replicas: Any,
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> Any:
    root = tmp_path / "media"
    media_config(monkeypatch, root)
    f = prepare_creative_common_basis(
        customer_engine, configuration, replicas, monkeypatch, root,
        platform="google_ads", selected_value="10", configured_runtime=True,
    )
    original = replicas[0]
    monkeypatch.setattr(app, "dependency_overrides", dict(original.app.dependency_overrides))
    assert get_media_store not in app.dependency_overrides
    assert vars(api)["PlanningDocumentService"] is PlanningDocumentService
    alice = TestClient(app, base_url=str(original.base_url))
    alice.cookies.update(original.cookies)
    return f, alice, f"/api/customer/v1/workspaces/{f.basis.workspace_id}/planning/plans"


def save(assembled: Any) -> tuple[Any, str]:
    f, alice, root = assembled
    result = alice.post(root, headers=headers(alice), json=f.body)
    assert result.status_code == 201, result.text
    return alice, root + "/" + result.json()["plan_id"]


@pytest.mark.parametrize(
    "damage", ["disabled", "invalid_mode", "relative_path", "missing", "corrupt"]
)
def test_byte_dependent_generation_refusal(
    assembled: Any, customer_engine: Engine, monkeypatch: pytest.MonkeyPatch, damage: str,
) -> None:
    f, _, _ = assembled
    alice, url = save(assembled)
    path = f.store.root / str(f.basis.workspace_id) / f.basis.media_sha256
    if damage in ("disabled", "invalid_mode"):
        monkeypatch.setattr(settings, "media_storage_mode", damage)
    elif damage == "relative_path":
        monkeypatch.setattr(settings, "media_local_directory", "relative-media")
    elif damage == "missing":
        path.unlink()
    else:
        path.chmod(0o600)
        path.write_bytes(b"corrupted")
    result = alice.post(url + "/generate", headers=headers(alice), json=generation())
    assert result.status_code == (409 if damage in ("missing", "corrupt") else 503), result.text
    if result.status_code == 503:
        assert result.json() == {"detail": "private media storage unavailable"}
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(PlanVersionRow)) == 0
        assert db.scalar(select(func.count()).select_from(PlanRequestRow).where(
            PlanRequestRow.operation == "generate"
        )) == 0


def test_no_images_need_no_store(
    assembled: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    f, _, _ = assembled
    f.body["inputs"]["creative"]["media_selections"] = []
    monkeypatch.setattr(settings, "media_storage_mode", "disabled")
    alice, url = save(assembled)
    result = alice.post(url + "/generate", headers=headers(alice), json=generation())
    assert result.status_code == 200, result.text
    doc = PlanVersion.model_validate(result.json()["document"])
    assert doc.creative_proof and not doc.creative_proof.basis.images
    assert not doc.advertising_writes_enabled and doc.spending_authority == "none"


def test_history_review_and_semantic_erasure(
    assembled: Any, customer_engine: Engine, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    f, alice, root = assembled
    reads = []
    real = LocalMediaStore.read_exact

    def read(store: LocalMediaStore, wid: int, sha: str, size: int) -> bytes:
        reads.append(wid)
        return real(store, wid, sha, size)

    monkeypatch.setattr(LocalMediaStore, "read_exact", read)
    alice, url = save(assembled)
    assert not reads
    generated = alice.post(url + "/generate", headers=headers(alice), json=generation())
    assert generated.status_code == 200, generated.text
    original = generated.json()
    assert reads == [f.basis.workspace_id]
    view = alice.get(url).json()
    action = view["document"]["actions"][0]
    decision = alice.post(url + "/decisions", headers=headers(alice), json=dict(
        expected_version=1, expected_event_sequence=0, document_digest=view["document_digest"],
        action_key=action["key"], action_digest=view["action_digests"][action["key"]],
        decision="accepted_for_manual_application", reason="Review creative brief manually",
        supersedes_event_id=None, request_key="configured-creative-review",
    ))
    assert decision.status_code == 200, decision.text
    (f.store.root / str(f.basis.workspace_id) / f.basis.media_sha256).unlink()
    monkeypatch.setattr(settings, "media_storage_mode", "disabled")
    retained = {}
    for name, suffix in [
        ("current", ""), ("history", "/versions/1"), ("export", "/export?version=1")
    ]:
        result = alice.get(url + suffix)
        assert result.status_code == 200, result.text
        assert result.json()["document"] == original["document"]
        doc = PlanVersion.model_validate(result.json()["document"])
        assert doc.digest() == result.json()["document_digest"]
        assert not doc.advertising_writes_enabled and doc.spending_authority == "none"
        retained[name] = result.json()
    replay = alice.post(url + "/generate", headers=headers(alice), json=generation())
    assert replay.status_code == 200 and replay.json() == original
    assert reads == [f.basis.workspace_id]
    with Session(customer_engine) as db, db.begin():
        bump_workspace_export_revision(db, f.basis.workspace_id)
    for model in (
        PlanRow, PlanInputRow, PlanVersionRow, PlanDependencyRow, PlanRequestRow, PlanEventRow
    ):
        with Session(customer_engine) as db:
            assert db.scalar(select(func.count()).select_from(model).where(
                model.workspace_id == f.basis.workspace_id
            )) == 0
    assert alice.get(url).status_code == 404
    erased = alice.post(url + "/generate", headers=headers(alice), json=generation())
    assert erased.status_code == 404
    assert reads == [f.basis.workspace_id]
    (tmp_path / "configured-creative-history.json").write_text(json.dumps(retained, indent=2))


@pytest.mark.parametrize("journey,platform", [
    ("google", "google_ads"), ("meta", "meta_ads"), ("tiktok", "tiktok_ads"),
    ("safety", "google_ads"),
])
def test_configured_creative_browser(
    customer_engine: Engine, request: pytest.FixtureRequest, configuration: Settings,
    replicas: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    journey: str, platform: Platform,
) -> None:
    media_config(monkeypatch, tmp_path / "media")
    browser.test_actual_creative_planning_browser(
        customer_engine, request, configuration, replicas, monkeypatch, tmp_path,
        journey, platform, configured_runtime=True,
    )
    assert vars(api)["PlanningDocumentService"] is PlanningDocumentService
    assert get_media_store not in app.dependency_overrides
    result = json.loads((tmp_path / "creative-browser-result.json").read_text())
    versions = result["retained_versions"]
    exported = result["browser"].get("exported", [])
    assert len(exported) == (0 if journey == "safety" else 2 if journey == "google" else 1)
    for item in versions + exported:
        doc = PlanVersion.model_validate(item["document"])
        assert doc.digest() == item["document_digest"]
        assert doc.policy_version == "inlet.descriptive-review.v5"
        assert doc.generator_version == "inlet.descriptive-planning.v5"
        assert not doc.advertising_writes_enabled and doc.spending_authority == "none"
    if exported:
        assert all(item["document_digest"] == exported[0]["document_digest"] for item in exported)
        by_version = {item["document"]["version"]: item for item in versions}
        for item in exported:
            stored = by_version[item["document"]["version"]]
            assert item["document"] == stored["document"]
            assert item["document_digest"] == stored["document_digest"]
        if journey == "google":
            assert set(by_version) == {1, 2}
            assert by_version[2]["document"]["parent_digest"] == by_version[1]["document_digest"]


def test_foreign_media_cannot_be_adopted(
    assembled: Any, customer_engine: Engine, replicas: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from copy import deepcopy

    from app.customers.models import CustomerMembership
    from app.workspaces.models import Workspace

    from tests.q16_fixture import IMAGE
    from tests.test_customer_identity import login

    f, alice, root = assembled
    bob_id = login(replicas[1], "configured-foreign-media:initial")
    with Session(customer_engine) as db, db.begin():
        foreign = Workspace(slug="configured-foreign", name="Foreign", client_name="Foreign")
        db.add(foreign)
        db.flush()
        wid = foreign.id
        db.add(CustomerMembership(user_id=bob_id, workspace_id=wid, role="owner"))
    # A second genuine fixture checkout/webhook uses distinct provider identities.
    from datetime import UTC, datetime

    from app.billing.contracts import CheckoutResult
    from app.billing.service import checkout, reconcile
    from app.billing.webhooks import receive

    from tests import test_customer_billing as billing

    class ForeignBilling(billing.FixtureBilling):
        def customer(self, workspace_id: int, idempotency_key: str) -> str:
            return "cus_configured_foreign"

        def checkout(
            self, customer_id: str, price_id: str, idempotency_key: str, return_url: str
        ) -> CheckoutResult:
            return super().checkout(customer_id, price_id, idempotency_key, return_url).model_copy(
                update={"id": "cs_configured_foreign"}
            )

    now = datetime.now(UTC)
    monkeypatch.setattr(billing, "NOW", now)
    transport = ForeignBilling()
    transport.state = transport.state.model_copy(update={
        "customer_id": "cus_configured_foreign", "subscription_id": "sub_configured_foreign"
    })
    payload = json.loads(billing.payload("evt_configured_foreign"))
    payload["data"]["object"].update(
        customer="cus_configured_foreign", id="sub_configured_foreign"
    )
    event = json.dumps(payload).encode()
    with Session(customer_engine) as db:
        checkout(db, wid, billing.POLICY, transport, "https://inlet.example/settings", now)
        assert receive(db, event, billing.signature(event, now), billing.SECRET, now)
        assert reconcile(db, wid, "evt_configured_foreign", billing.POLICY, transport, now)
    bob = TestClient(app, base_url=str(alice.base_url))
    bob.cookies.update(replicas[1].cookies)
    path = f"/api/customer/v1/workspaces/{wid}/media"
    uploaded = bob.post(path, headers=headers(bob), content=IMAGE.read_bytes())
    assert uploaded.status_code == 200, uploaded.text
    item = uploaded.json()
    assert alice.get(path + "/" + item["media_id"]).status_code in {403, 404}
    assert bob.get(root).status_code in {403, 404}

    def forbidden(*args: Any) -> bytes:
        raise AssertionError("foreign media must fail before bytes")

    monkeypatch.setattr(LocalMediaStore, "read_exact", forbidden)
    body = deepcopy(f.body)
    body["inputs"]["creative"]["media_selections"] = [dict(
        media_id=item["media_id"], expected_sha256=item["sha256"]
    )]
    rejected = alice.post(root, headers=headers(alice), json=body)
    assert rejected.status_code == 409, rejected.text
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(PlanRow)) == 0
