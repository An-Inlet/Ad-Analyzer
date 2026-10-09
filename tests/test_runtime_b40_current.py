"""Current reads/local confirmations and explicit denials, not historical execution."""

from datetime import timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from app.production_runtime import optimization_mandates
from app.settings import Settings
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from tests.current_runtime_read_contexts import current_tiktok_source as current_tiktok_source
from tests.optimization_current_read_fixture import configured
from tests.optimization_source_retained_fixture import retained_optimization_source_fixture
from tests.test_campaign_video import encoded as encoded
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration
from tests.tiktok_current_read_fixture import configured_tiktok_customer
from tests.tiktok_draft_retained_fixture import retained_tiktok_draft_fixture
from tests.tiktok_linked_current_read_fixture import configured_linked_customer

DISABLED = "advertising_writes_disabled_in_planning_mvp"


@pytest.mark.planning_boundary
@pytest.mark.parametrize("provider", ["google_ads", "meta_ads"])
def test_current_optimization_boundaries(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: Any,
) -> None:
    with retained_optimization_source_fixture(customer_engine, tmp_path / "source", provider) as (
        engine,
        ids,
        media,
    ):
        clients = cast(Any, replicas).__wrapped__(engine, monkeypatch)
        try:
            alice, base, query, wire, control = configured(
                engine, configuration, media, monkeypatch, clients, ids
            )
            opt = base + "/optimization"
            options = alice.post(opt + "/target-options", json=query, headers=headers(alice))
            assert options.status_code == 200, options.text
            assert len(options.json()["options"]) == 1 and wire.calls
            selected = {**query, "option_id": options.json()["options"][0]["id"]}
            callbacks: list[bool] = []

            def forbidden(*args: Any, **kwargs: Any) -> Any:
                callbacks.append(True)
                raise AssertionError("planning route must not enter preparation finalizer")

            monkeypatch.setattr(optimization_mandates, "final", forbidden)
            before = len(wire.calls)
            for endpoint, body in (
                (
                    "/budget-mandates",
                    {
                        "intent": {
                            "selection": selected,
                            "total_cap_micros": 50_000_000,
                            "aggressiveness": "balanced",
                        }
                    },
                ),
                ("/budget-mandates/" + "a" * 32 + "/consent", {}),
                ("/mandates", {}),
                ("/mandates/" + "a" * 32 + "/consent", {}),
                ("/initial-reviews", {}),
                ("/repeat-reviews", {}),
            ):
                response = alice.post(opt + endpoint, json=body, headers=headers(alice))
                assert response.status_code == 409, response.text
                assert response.json()["detail"] == DISABLED
            assert callbacks == [] and len(wire.calls) == before
            assert control["opened"] == control["closed"]
            assert not wire.google.writes and not wire.meta.posts
            with Session(engine) as db:
                for table in (
                    "optimization_mandate_preparations",
                    "provider_execution_revisions",
                    "provider_period_ledgers",
                ):
                    assert db.scalar(text(f"SELECT count(*) FROM {table}")) == 0
        finally:
            clients[0].close()
            clients[1].close()


@pytest.mark.planning_boundary
@pytest.mark.parametrize("change", ["session", "generation", "source_before_read"])
def test_current_optimization_read_invalidation(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    import time

    from app.customers.access import SESSION_COOKIE, digest
    from app.customers.models import CustomerSession
    from app.google_connections.models import GoogleCustomerConnection
    from app.production_runtime import optimization_assembly

    with retained_optimization_source_fixture(customer_engine, tmp_path / "source") as (
        engine,
        ids,
        media,
    ):
        clients = cast(Any, replicas).__wrapped__(engine, monkeypatch)
        try:
            alice, base, query, wire, control = configured(
                engine, configuration, media, monkeypatch, clients, ids
            )
            endpoint = base + "/optimization/target-options"
            assert alice.post(endpoint, json=query, headers=headers(alice)).status_code == 200
            calls: list[bool] = []
            before = len(wire.calls)

            def invalidate() -> None:
                calls.append(True)
                with Session(engine) as db:
                    if change == "session":
                        row = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
                        assert row
                        row.revoked_at = int(time.time())
                    else:
                        source = db.scalar(select(GoogleCustomerConnection))
                        assert source
                        source.generation += 1
                    db.commit()

            if change == "source_before_read":
                monkeypatch.setattr(
                    optimization_assembly, "registered_optimization_evidence", lambda _: None
                )
            else:
                control["callback"] = invalidate
            response = alice.post(endpoint, json=query, headers=headers(alice))
            assert response.status_code == 409, response.text
            if change == "source_before_read":
                assert response.json()["detail"] == {
                    "code": "optimization_runtime_unavailable",
                    "message": "Provider execution is unavailable.",
                }
                assert len(wire.calls) == before and calls == []
            else:
                assert response.json()["detail"]["code"] == "owned_target_catalog_unavailable"
                assert calls == [True]
            assert control["opened"] == control["closed"]
            assert not wire.google.writes
        finally:
            clients[0].close()
            clients[1].close()


@pytest.mark.planning_boundary
@pytest.mark.parametrize("linked", [False, True])
def test_current_tiktok_local_configuration(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    encoded: Any,
    linked: bool,
) -> None:
    with retained_tiktok_draft_fixture(customer_engine, tmp_path / "source", encoded()) as (
        engine,
        ids,
        media,
    ):
        clients = cast(Any, replicas).__wrapped__(engine, monkeypatch)
        try:
            build = configured_linked_customer if linked else configured_tiktok_customer
            alice, base, _, draft, revision, server, requests, control = build(
                engine, configuration, media, monkeypatch, clients, ids
            )
            prefix = base + ("/tiktok/linked" if linked else "/social")
            options = alice.post(
                prefix + "/options",
                json={"draft_id": draft, "draft_revision": revision},
                headers=headers(alice),
            )
            assert options.status_code == 200, options.text
            answer = (
                dict(
                    kind="tiktok_linked_push",
                    reviewed_video_and_cover=True,
                    commercial_music_rights_reviewed=True,
                    creates_new_linked_post_reviewed=True,
                    ads_only_visibility_reviewed=True,
                )
                if linked
                else dict(kind="tiktok_cover", reviewed_pair=True)
            )
            prepared = alice.post(
                prefix + "/reviews",
                json={
                    "draft_id": draft,
                    "draft_revision": revision,
                    "option_id": options.json()["options"][0]["id"],
                    "answer": answer,
                    "cover_media_id": control["cover_id"],
                },
                headers=headers(alice),
            )
            assert prepared.status_code == 201, prepared.text
            saved = prepared.json()
            if linked:
                assert saved["financial_qualification"] == "not_assessed"
                assert saved["spending_authority"] == "none"
                control["now"] += timedelta(seconds=10)
            confirmed = alice.post(
                prefix + f"/reviews/{saved['id']}/confirmation",
                json={"expected_digest": saved["digest"], "acknowledged": True},
                headers=headers(alice),
            )
            assert confirmed.status_code == 200, confirmed.text
            assert alice.get(prefix + f"/reviews/{saved['id']}").status_code == 200
            creation = alice.post(
                prefix + "/creation-reviews",
                json={
                    "configuration_review_id": saved["id"],
                    "expected_configuration_digest": saved["digest"],
                    "mandate_id": "a" * 32,
                    "mandate_revision": 1,
                },
                headers=headers(alice),
            )
            assert creation.status_code == (404 if linked else 409), creation.text
            assert creation.json()["detail"] == (
                "provider mandate unavailable" if linked else DISABLED
            )
            before = len(requests)
            for path in (
                "/mandates",
                "/activation-reviews",
                "/reviews/" + "a" * 32 + "/approval",
                "/reviews/" + "a" * 32 + "/runs",
                "/runs/" + "a" * 32 + "/advance",
            ):
                denied = alice.post(base + path, json={}, headers=headers(alice))
                assert denied.status_code == 409, denied.text
                assert denied.json()["detail"] == DISABLED
            assert len(requests) == before
            assert server.posts == server.activations == 0
            assert control["opened"] == control["closed"]
            if linked:
                assert requests and all(r.method == "GET" for r in requests)
        finally:
            clients[0].close()
            clients[1].close()


@pytest.mark.planning_boundary
def test_current_composition_is_lazy_and_environment_exact(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    encoded: Any,
    current_tiktok_source: Any,
) -> None:
    customer_engine, tmp_path, replicas, ids = current_tiktok_source
    import json

    from app.production_runtime import provider_composition
    from app.production_runtime.meta_configuration import MetaConfigurationBundleV1
    from app.production_runtime.meta_contracts import (
        MetaEvidenceDescriptor,
        RegisteredMetaEvidenceSource,
    )
    from app.settings import settings

    from tests.test_meta_runtime_contracts import bundle_document, manifest

    alice, base, _, draft, revision, _, requests, control = configured_tiktok_customer(
        customer_engine, configuration, tmp_path, monkeypatch, replicas, ids
    )
    document = bundle_document()
    selected = manifest(MetaConfigurationBundleV1.from_document(document))
    descriptor = MetaEvidenceDescriptor(
        source_id=selected.evidence_source_id,
        profile_digest=selected.evidence_profile_digest,
        environment="contract_test",
        kind="contract_scenario",
    )

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("TikTok must not construct the unused Meta source")

    registered = RegisteredMetaEvidenceSource(descriptor, forbidden)
    monkeypatch.setattr(provider_composition, "registered_meta_evidence", lambda _: registered)
    mp, bp = tmp_path / "coexist-meta.json", tmp_path / "coexist-meta-bundle.json"
    mp.write_text(selected.model_dump_json())
    bp.write_text(json.dumps(document))
    monkeypatch.setattr(settings, "meta_execution_manifest_path", str(mp))
    monkeypatch.setattr(settings, "meta_execution_manifest_digest", selected.digest())
    monkeypatch.setattr(settings, "meta_execution_bundle_path", str(bp))
    capability = alice.get(base + "/capabilities")
    assert capability.status_code == 200, capability.text
    assert [p["available"] for p in capability.json()["providers"]] == [False, False, False]
    assert capability.json()["activation_available"] is False
    assert capability.json()["scope"] == "planning_only"
    assert control["builds"] == 0 and requests == []
    result = alice.post(
        base + "/social/options",
        headers=headers(alice),
        json={"draft_id": draft, "draft_revision": revision},
    )
    assert result.status_code == 200, result.text
    assert "tiktok_native_catalog_parser_unverified" in result.json()["blockers"]
    assert control["builds"] == 1 and requests == []
    live = selected.model_copy(update={"environment": "live", "live_execution_enabled": True})
    mp.write_text(live.model_dump_json())
    monkeypatch.setattr(settings, "meta_execution_manifest_digest", live.digest())
    denied = alice.get(base + "/capabilities")
    assert denied.status_code == 409
    assert denied.json()["detail"] == "provider_execution_environment_mismatch"
    assert control["builds"] == 1 and control["opened"] == control["closed"]
