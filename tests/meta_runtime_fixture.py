"""Real configured Meta APIs with explicit scenario evidence and actual MockHTTP."""

import base64
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount
from app.api.customer_execution import router
from app.api.customer_social_execution import router as social_router
from app.api.customer_social_review import router as review_router
from app.campaign_review import service as source
from app.campaign_review.contracts import RevisionInput
from app.campaign_review.storage import LocalMediaStore
from app.customers.models import CustomerUser
from app.mandates import service as simulation
from app.mandates.models import Mandate
from app.mandates.schemas import AccountScope
from app.meta.models import MetaConnection
from app.meta.security import Vault
from app.production_runtime import assembly, provider_composition
from app.production_runtime.meta_configuration import MetaConfigurationBundleV1
from app.production_runtime.meta_contracts import (
    MetaEvidenceDescriptor,
    MetaExecutionEvidence,
    RegisteredMetaEvidenceSource,
)
from app.publication import execution_mandates
from app.publication.coordinator_contracts import ConfigurationQualification
from app.publication.customer_intents import account as owned_account
from app.publication.exposure_qualification import (
    AccountExposureFact,
    PortfolioExposureReader,
    PortfolioFacts,
    QualificationProfile,
)
from app.publication.scoped_media import ScopedProviderMediaReader
from app.settings import Settings, settings
from app.workspaces.models import WorkspaceIntegration
from pydantic import SecretStr
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_campaign_review import png
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import ISSUER, login
from tests.test_meta_runtime_contracts import bundle_document, manifest
from tests.test_provider_execution_mandates import setup
from tests.test_social_activation_journeys import Server
from tests.test_social_publication_http import reviewed


def configured_meta_customer(
    engine: Engine, config: Settings, path: Path, monkeypatch: pytest.MonkeyPatch, replicas: Any
) -> Any:
    alice, _, _ = replicas
    monkeypatch.setattr(
        settings,
        "meta_token_encryption_key",
        SecretStr(base64.urlsafe_b64encode(b"m" * 32).decode()),
    )
    monkeypatch.setattr(settings, "media_storage_mode", "local_dev")
    monkeypatch.setattr(settings, "media_local_directory", str(path))
    with Session(engine) as db:
        policy, actor = setup(db, config, path, goal_budget_micros=100_000_000)
        wid = policy.workspace_id
        user = db.get(CustomerUser, actor)
        assert user
        user.issuer, user.subject = ISSUER, "configured-meta"
        integration = WorkspaceIntegration(
            workspace_id=wid,
            integration_key="configured-meta",
            provider="meta_ads",
            display_name="Offline Meta",
            status="active",
            configuration={},
        )
        db.add(integration)
        db.flush()
        account = AdvertisingAccount(
            workspace_id=wid,
            connection_id=integration.id,
            platform=AdvertisingPlatform("meta_ads"),
            external_account_id="1234567890",
            name="Offline",
            currency_code="USD",
            time_zone="UTC",
        )
        db.add(account)
        db.flush()
        native = MetaConnection(
            workspace_id=wid,
            workspace_integration_id=integration.id,
            account_id=account.id,
            external_account_id=account.external_account_id,
            encrypted_credentials=Vault(settings).seal(
                wid,
                account.external_account_id,
                {
                    "access_token": "offline-meta-access",
                    "expires_at": (NOW + timedelta(hours=2)).isoformat(),
                },
            ),
        )
        db.add(native)
        db.flush()
        scope = AccountScope(
            platform="meta_ads", connection_id=integration.id, account_id=account.id
        )
        old = db.scalar(select(Mandate).where(Mandate.workspace_id == wid))
        assert old
        sim = simulation.policy(db, old).model_copy(
            update={
                "accounts": [scope],
                "total_cap_micros": 100_000_000,
                "per_action_cap_micros": 80_000_000,
                "positive_change_cap_micros": 20_000_000,
            }
        )
        simulation.edit(db, old, old.revision, sim, actor, NOW)
        simulation.approve(db, old, old.revision, actor, NOW)
        db.commit()
        store = LocalMediaStore(path)
        media = source.upload(db, wid, actor, png(), store, NOW)
        content = reviewed().source.definition.content.model_dump()
        content["media"] = {"media_id": media.id, "sha256": media.sha256}
        revision = source.revise(
            db,
            wid,
            RevisionInput(
                account=scope,
                mandate_id=old.id,
                mandate_revision=old.revision,
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
        draft, rev = revision.draft_id, revision.revision
        media_binding = ScopedProviderMediaReader(db, store).binding(wid, media.id)
        policy = policy.model_copy(
            update={
                "accounts": [owned_account(db, wid, account.id)],
                "total_cap_micros": 100_000_000,
                "per_plan_cap_micros": 80_000_000,
                "positive_change_cap_micros": 20_000_000,
            }
        )
        db.commit()
    document = bundle_document()
    # Match the reviewed creative language set exactly.
    bundle = MetaConfigurationBundleV1.from_document(document)
    selected = manifest(bundle)
    mp, bp = path / "meta-manifest.json", path / "meta-bundle.json"
    mp.write_text(selected.model_dump_json())
    bp.write_text(json.dumps(document))
    monkeypatch.setattr(settings, "meta_execution_manifest_path", str(mp))
    monkeypatch.setattr(settings, "meta_execution_manifest_digest", selected.digest())
    monkeypatch.setattr(settings, "meta_execution_bundle_path", str(bp))
    monkeypatch.setattr(assembly, "execution_clock", lambda: NOW)
    descriptor = MetaEvidenceDescriptor(
        source_id=selected.evidence_source_id,
        profile_digest=selected.evidence_profile_digest,
        environment="contract_test",
        kind="contract_scenario",
    )
    control: dict[str, Any] = {"builds": 0, "opened": 0, "closed": 0}
    server = Server("meta_ads")
    server.media = {"image": media_binding}
    requests: list[httpx.Request] = []

    def wire(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        callback = control.pop("callback", None)
        if callback:
            callback()
        if request.method == "GET" and request.url.path == "/v26.0/act_1234567890":
            return httpx.Response(
                200,
                json={
                    "account_id": "1234567890",
                    "account_status": 1,
                    "currency": "USD",
                    "timezone_name": "UTC",
                },
            )
        if request.url.path.endswith("/promote_pages"):
            return httpx.Response(200, json={"data": [{"id": "41", "name": "Owned Page"}]})
        if request.url.path.endswith("/adspixels"):
            return httpx.Response(200, json={"data": [{"id": "42", "name": "Owned Pixel"}]})
        return server(request)

    class Tracked(httpx.MockTransport):
        def close(self) -> None:
            control["closed"] += 1
            super().close()

    def transport(manifest: Any) -> httpx.BaseTransport:
        assert manifest.environment == "contract_test"
        control["opened"] += 1
        return Tracked(wire)

    def build(sessions: Any, authorize: Any, actor_id: str, clock: Any) -> MetaExecutionEvidence:
        control["builds"] += 1

        def qualify(plan: Any, now: Any) -> ConfigurationQualification:
            # Explicit offline configuration scenario, never live provider qualification.
            assert plan.review.scope.account.platform == "meta_ads"
            assert plan.review.qualification_blockers
            return ConfigurationQualification(
                environment="contract_test",
                account=policy.accounts[0],
                plan_digest=plan.digest(),
                api_version=plan.api_version,
                observed_at=now,
                expires_at=now + timedelta(seconds=60),
                evidence_digest=plan.digest(),
                checks_version="explicit_meta_fixture_not_live_v1",
                unresolved=[],
            )

        def facts(db: Session, binding: Any, plan: Any, now: Any) -> PortfolioFacts:
            authorize(db, wid, actor_id)
            _, current = execution_mandates.checked(db, wid, binding, actor_id, clock)
            return PortfolioFacts(
                qualification_id="f" * 32,
                profile_id="explicit_meta_scenario",
                environment="contract_test",
                plan_digest=plan.digest(),
                accounts=[
                    AccountExposureFact(
                        account=a,
                        reported_spend_micros=0,
                        unreported_upper_micros=0,
                        unchanged_future_upper_micros=0,
                        reporting_watermark=now,
                    )
                    for a in current.accounts
                ],
                complete=True,
                currency=current.currency,
                period_start=current.starts_at,
                period_end=current.ends_at,
                observed_at=now,
                expires_at=now + timedelta(seconds=60),
                budget_owner_key="new/meta/" + plan.digest(),
                target_set_digest=plan.digest(),
                proposed_owner_upper_micros=plan.review.configuration.reservation_micros,
            )

        reader = PortfolioExposureReader(
            facts,
            {
                "explicit_meta_scenario": QualificationProfile(
                    environment="contract_test",
                    model_version="explicit_fixture_only",
                    semantics="contract_scenario",
                    maximum_age_seconds=60,
                )
            },
            clock=clock,
        )
        return MetaExecutionEvidence(descriptor, qualify, reader, reader.for_activation)

    registered = RegisteredMetaEvidenceSource(descriptor, build)
    monkeypatch.setattr(
        provider_composition,
        "registered_meta_evidence",
        lambda name: registered if name == descriptor.source_id else None,
    )
    monkeypatch.setattr(provider_composition, "meta_execution_transport", transport)
    for item in (router, social_router, review_router):
        alice.app.include_router(item)
    login(alice, "configured-meta:1")
    body = policy.model_dump(
        mode="json",
        exclude={
            "schema_version",
            "environment",
            "workspace_id",
            "accounts",
            "freshness_seconds",
            "allowed_target_set_digest",
            "campaign_and_creative_policy",
            "activation_policy",
        },
    )
    body["account_ids"] = [policy.accounts[0].account.account_id]
    return (
        alice,
        f"/api/customer/v1/workspaces/{wid}/execution",
        body,
        draft,
        rev,
        server,
        requests,
        control,
    )
