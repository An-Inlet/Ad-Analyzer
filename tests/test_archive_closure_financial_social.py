"""Owned HTTP archive/closure over actual offline financial and social records."""

import io
import json
from collections.abc import Generator
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from app.api import customer_exports
from app.api.customer import router as customer_router
from app.api.customer_execution import router as execution_router
from app.api.customer_lifecycle import router as lifecycle_router
from app.campaign_review import service as source
from app.campaign_review.contracts import RevisionInput
from app.campaign_review.storage import LocalMediaStore
from app.customers.access import CSRF_COOKIE
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerUser
from app.database.session import get_db
from app.mandates import service as simulation
from app.mandates.models import Mandate
from app.publication import optimization as o
from app.publication import replacement as replacement
from app.publication.customer_optimization_catalog import ConfiguredOptimizationCatalog
from app.publication.customer_optimization_contracts import (
    CustomerOptimizationRuntime,
    get_customer_optimization_runtime,
)
from app.publication.execution_authorization import owner_authorizer
from app.publication.execution_models import (
    ProviderExecutionReceipt,
    ProviderExposureReservation,
    ProviderPeriodLedger,
    ProviderReservationReplacement,
)
from app.publication.replacement_contracts import RepeatOptimizationReview
from app.publication.scoped_media import ScopedProviderMediaReader
from app.publication.social_catalog import (
    MetaCatalogOption,
    MetaConfigurationProfile,
    SocialCatalog,
)
from app.publication.social_contracts import MetaImagePublicationFields
from app.publication.social_customer_producer import catalog_request
from app.publication.social_review_contracts import MetaNoDSAAnswer, SocialRequirements
from app.publication.social_review_models import (
    SocialConfigurationApproval,
    SocialConfigurationReview,
)
from app.publication.social_review_service import confirm, prepare, selection
from app.settings import Settings, settings
from app.shopify.models import ShopifyConnection
from app.workspaces.models import Workspace
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_campaign_review import png
from tests.test_commerce_measurement import NOW
from tests.test_customer_exports import export_engine as export_engine
from tests.test_customer_exports import unpack
from tests.test_customer_identity import ISSUER, ORIGIN, FakeProvider, login
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_durable_optimization import ready
from tests.test_repeat_optimization import admit, reader
from tests.test_shopify_sales import configuration as configuration
from tests.test_social_publication_http import reviewed


def social_approval(db: Session, wid: int, actor: str, scope: Any, store: LocalMediaStore) -> str:
    """Actual approved source and strict no-DSA confirmation; no production rule claim."""
    mandate = db.scalar(select(Mandate).where(Mandate.workspace_id == wid))
    assert mandate is not None
    policy = simulation.policy(db, mandate).model_copy(
        update={
            "accounts": [scope.account],
            "total_cap_micros": 100_000_000,
            "per_action_cap_micros": 80_000_000,
            "positive_change_cap_micros": 20_000_000,
        }
    )
    simulation.edit(db, mandate, mandate.revision, policy, actor, NOW)
    simulation.approve(db, mandate, mandate.revision, actor, NOW)
    db.commit()
    media = source.upload(db, wid, actor, png(), store, NOW)
    template = reviewed()
    content = template.source.definition.content.model_dump()
    content["media"] = {"media_id": media.id, "sha256": media.sha256}
    revision = source.revise(
        db,
        wid,
        RevisionInput(
            account=scope.account,
            mandate_id=mandate.id,
            mandate_revision=mandate.revision,
            currency="USD",
            budget_micros=40_000_000,
            starts_at=NOW,
            ends_at=NOW + timedelta(hours=1),
            content=content,
        ),
        actor,
        store,
        NOW,
    )
    source.approve(
        db, wid, revision.draft_id, revision.revision, revision.digest, actor, store, NOW
    )
    _, artifact = source.preview(db, wid, revision.draft_id, store, NOW)
    fields = template.configuration
    assert isinstance(fields, MetaImagePublicationFields)
    profile = MetaConfigurationProfile(
        profile_id="offline_no_dsa",
        label="Offline No-DSA Test",
        currency="USD",
        currency_exponent=2,
        language_locale_ids=fields.language_locale_ids,
        attribution=fields.attribution,
        age_min=fields.age_min,
        age_max=fields.age_max,
        dsa_required=False,
        url_tags=fields.url_tags,
    )
    option = MetaCatalogOption(
        label="Owned Page / Pixel",
        profile_digest=profile.digest(),
        page_id=fields.page_id,
        pixel_id=fields.pixel_id,
    )
    request = catalog_request(artifact, scope)
    catalog = SocialCatalog(
        request=request,
        observed_at=NOW,
        expires_at=NOW + timedelta(minutes=1),
        currency="USD",
        account_timezone="UTC",
        options=[option],
        unavailable_reasons=[],
        qualification_blockers=["native_configuration_unqualified"],
        discovery_evidence="meta_account_edges",
    )
    document = selection(
        db,
        wid,
        actor,
        scope,
        catalog,
        option.identifier(request),
        profile,
        SocialRequirements(
            profile_digest=profile.digest(),
            requirements_digest="a" * 64,
            wording_version="offline-only-v1",
            verified=True,
            dsa_required=False,
            wording="Offline Test: Review This Exact No-DSA Configuration.",
        ),
        MetaNoDSAAnswer(special_category_answer="none_applicable"),
        None,
        "contract_test",
        store,
        lambda: NOW,
        owner_authorizer,
    )
    row = prepare(db, wid, actor, document, lambda: NOW, owner_authorizer)
    confirm(db, wid, row.id, row.digest, actor, document, lambda: NOW, owner_authorizer)
    db.commit()
    assert document.primary == ScopedProviderMediaReader(db, store).binding(wid, media.id)
    return row.id


def test_owned_archive_then_closure_retains_replacement_and_social_evidence(
    export_engine: Engine, configuration: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = LocalMediaStore(tmp_path)
    with Session(export_engine) as db:
        brands = []
        for name in ("brand-a", "brand-b"):
            wid, actor, binding, scope, target, action, runtime, server = ready(
                db, configuration, tmp_path, "meta_ads" if name == "brand-a" else "google_ads"
            )
            user = db.get(CustomerUser, actor)
            workspace = db.get(Workspace, wid)
            assert user is not None and workspace is not None
            user.issuer, user.subject = ISSUER, name
            for connection in db.scalars(select(ShopifyConnection)):
                connection.shop_domain = f"brand-{connection.id}.myshopify.com"
            workspace.name = name
            for existing_workspace in db.scalars(select(Workspace)):
                existing_workspace.slug = f"{name}-{existing_workspace.id}"
            db.commit()
            row = o.prepare_optimization(
                db, wid, binding, scope, target, action, "a" * 64, actor, runtime, lambda: NOW
            )
            run, claim = admit(db, wid, actor, row, runtime)
            assert (
                o.execute_claim(db, claim, actor, runtime, lambda: NOW).outcome
                == "verified_target_state"
            )
            runtime = replace(runtime, replacement_reader=reader(runtime))
            review = replacement.prepare_repeat_optimization(
                db,
                wid,
                binding,
                scope,
                run.reservation_id,
                target,
                action.model_copy(update={"amount_micros": 44_000_000}),
                "b" * 64,
                actor,
                runtime,
                lambda: NOW,
            )
            o.approve_optimization(
                db, wid, review.id, review.digest, review.plan_digest, actor, runtime, lambda: NOW
            )
            successor = o.create_run(db, wid, review.id, actor, runtime, lambda: NOW)
            replacement.transfer(
                db,
                wid,
                successor,
                RepeatOptimizationReview.model_validate(review.document),
                actor,
                runtime,
                lambda: NOW,
            )
            successor_claim = None
            social_id = social_approval(db, wid, actor, scope, store) if name == "brand-a" else ""
            brands.append((wid, actor, successor.id, successor_claim, runtime, server, social_id))
        a, b = brands
        expected_holds = {
            r.id: (r.state, r.amount_micros)
            for r in db.scalars(select(ProviderExposureReservation))
        }
        audit_ids = set(db.scalars(select(ProviderReservationReplacement.id)))
        social_row = db.get(SocialConfigurationReview, a[6])
        social_confirmation = db.get(SocialConfigurationApproval, a[6])
        assert social_row is not None and social_confirmation is not None
        expected_social = social_row.document
        expected_confirmation = social_confirmation.digest
        expected_audit = db.scalar(
            select(ProviderReservationReplacement).where(
                ProviderReservationReplacement.workspace_id == a[0]
            )
        )
        assert expected_audit is not None
        expected_audit_document = expected_audit.document
        receipt_ids = set(
            db.scalars(
                select(ProviderExecutionReceipt.id).where(
                    ProviderExecutionReceipt.workspace_id == a[0]
                )
            )
        )
        ledger_values = {
            r.id: (r.spent_high_water_micros, r.action_count)
            for r in db.scalars(select(ProviderPeriodLedger))
        }

    monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)
    monkeypatch.setattr(customer_exports, "get_media_store", lambda: store)
    app = FastAPI()
    app.include_router(customer_router)
    app.include_router(customer_exports.router)
    app.include_router(lifecycle_router)
    app.include_router(execution_router)

    def optimization_runtime(request: Request) -> CustomerOptimizationRuntime:
        brand = next(item for item in brands if item[0] == int(request.path_params["workspace_id"]))
        return CustomerOptimizationRuntime(
            brand[4], ConfiguredOptimizationCatalog(brand[4], ()), lambda: NOW
        )

    app.dependency_overrides[get_customer_optimization_runtime] = optimization_runtime

    def database() -> Generator[Session, None, None]:
        with Session(export_engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_identity_provider] = FakeProvider
    with TestClient(app, base_url=ORIGIN) as alice, TestClient(app, base_url=ORIGIN) as bob:
        assert login(alice, "brand-a:1") == a[1]
        assert login(bob, "brand-b:1") == b[1]
        headers = {
            "Origin": ORIGIN,
            "X-CSRF-Token": alice.cookies[CSRF_COOKIE],
            "Idempotency-Key": "archive-replacement-social",
        }
        base = f"/api/customer/v1/workspaces/{a[0]}"
        response = alice.post(base + "/exports", json={}, headers=headers)
        assert response.status_code == 200, response.text
        export_id = response.json()["request_id"]
        download = base + f"/exports/{export_id}/download"
        assert bob.get(download).status_code in {403, 404}
        response = alice.get(download)
        assert response.status_code == 200, response.text
        manifest, entries = unpack(io.BytesIO(response.content))
        assert manifest["supported_customer_data_complete"], [
            s for s in manifest["sections"] if not s["complete"]
        ]
        for entry, payload in entries.items():
            if entry.startswith("data/") and entry.endswith(".jsonl"):
                for line in payload.splitlines():
                    record = json.loads(line)
                    if "workspace_id" in record:
                        assert record["workspace_id"] == a[0], entry
        for table in (
            "provider_reservation_replacements",
            "customer_social_configuration_reviews",
            "customer_social_configuration_approvals",
        ):
            rows = [json.loads(line) for line in entries[f"data/{table}.jsonl"].splitlines()]
            assert len(rows) == 1 and all(row["workspace_id"] == a[0] for row in rows)
        assert (
            json.loads(entries["data/provider_reservation_replacements.jsonl"].splitlines()[0])[
                "document"
            ]
            == expected_audit_document
        )
        assert (
            json.loads(entries["data/customer_social_configuration_reviews.jsonl"].splitlines()[0])[
                "document"
            ]
            == expected_social
        )
        assert (
            json.loads(
                entries["data/customer_social_configuration_approvals.jsonl"].splitlines()[0]
            )["digest"]
            == expected_confirmation
        )
        assert a[6].encode() in entries["data/customer_social_configuration_reviews.jsonl"]
        assert b[2].encode() not in b"".join(entries.values())
        headers["Idempotency-Key"] = "closure-replacement-social"
        preview = alice.post(base + "/closure-preview", json={}, headers=headers)
        assert preview.status_code == 200, preview.text
        data = preview.json()
        closed = alice.post(
            base + f"/closures/{data['request_id']}/confirm",
            headers=headers,
            json={
                "expected_revision": data["revision"],
                "inventory_digest": data["inventory_digest"],
                "confirm_workspace_id": a[0],
            },
        )
        assert closed.status_code == 200, closed.text
        assert closed.json()["state"] == "blocked" and closed.json()["closed"] is False
        assert bob.get("/api/customer/v1/session").status_code == 200
        assert alice.get("/api/customer/v1/session").status_code == 200
        assert bob.get(base + f"/closures/{data['request_id']}").status_code in {403, 404}
        status = alice.get(base + f"/closures/{data['request_id']}")
        assert status.status_code == 200 and status.json()["closed"] is False

        denied = alice.post(base + f"/execution/runs/{a[2]}/advance", headers=headers)
        assert denied.status_code in {403, 404, 409}, denied.text
        assert len(a[5].posts) == 1
        progressed = bob.post(
            f"/api/customer/v1/workspaces/{b[0]}/execution/runs/{b[2]}/advance",
            headers={"Origin": ORIGIN, "X-CSRF-Token": bob.cookies[CSRF_COOKIE]},
        )
        assert progressed.status_code == 200, progressed.text
        assert len(b[5].writes) == 2
        with Session(export_engine) as db:
            assert {
                r.id: (r.state, r.amount_micros)
                for r in db.scalars(select(ProviderExposureReservation))
            } == expected_holds
            assert set(db.scalars(select(ProviderReservationReplacement.id))) == audit_ids
            retained_review = db.get(SocialConfigurationReview, a[6])
            retained_confirmation = db.get(SocialConfigurationApproval, a[6])
            assert retained_review is not None and retained_review.document == expected_social
            assert (
                retained_confirmation is not None
                and retained_confirmation.digest == expected_confirmation
            )
            assert (
                set(
                    db.scalars(
                        select(ProviderExecutionReceipt.id).where(
                            ProviderExecutionReceipt.workspace_id == a[0]
                        )
                    )
                )
                == receipt_ids
            )
            assert {
                r.id: (r.spent_high_water_micros, r.action_count)
                for r in db.scalars(select(ProviderPeriodLedger))
            } == ledger_values
