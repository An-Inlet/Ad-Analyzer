"""Ordinary configured Google APIs; only explicit scenario evidence and HTTP are injected."""

import base64
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.ads.models import AdvertisingAccount
from app.api.customer_execution import router
from app.campaign_review.models import CampaignDraft
from app.customers.models import CustomerUser
from app.google_connections.models import GoogleCustomerConnection
from app.google_connections.security import Vault
from app.production_runtime import assembly
from app.production_runtime.contracts import (
    GoogleEvidenceDescriptor,
    GoogleExecutionEvidence,
    GoogleExecutionManifestV1,
    RegisteredGoogleEvidenceSource,
)
from app.publication import execution_mandates
from app.publication.exposure_qualification import (
    AccountExposureFact,
    PortfolioExposureReader,
    PortfolioFacts,
    QualificationProfile,
)
from app.settings import Settings, settings
from pydantic import SecretStr
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import ISSUER, login
from tests.test_google_activation import Server
from tests.test_google_runtime_contracts import manifest
from tests.test_provider_execution_mandates import setup
from tests.test_provider_qualification import response_rows


def configured_customer(
    engine: Engine, config: Settings, path: Path, monkeypatch: pytest.MonkeyPatch, replicas: Any
) -> Any:
    alice, _, provider = replicas
    monkeypatch.setattr(settings, "google_customer_client_id", "offline-client")
    monkeypatch.setattr(settings, "google_customer_client_secret", SecretStr("offline-secret"))
    monkeypatch.setattr(
        settings,
        "google_customer_encryption_key",
        SecretStr(base64.urlsafe_b64encode(b"g" * 32).decode()),
    )
    monkeypatch.setattr(settings, "media_storage_mode", "local_dev")
    monkeypatch.setattr(settings, "media_local_directory", str(path))
    with Session(engine) as db:
        policy, actor = setup(db, config, path)
        user = db.get(CustomerUser, actor)
        assert user
        user.issuer, user.subject = ISSUER, "configured-google"
        account = db.get(AdvertisingAccount, policy.accounts[0].account.account_id)
        assert account
        account.time_zone = "Pacific/Pago_Pago"
        native = db.scalar(
            select(GoogleCustomerConnection).where(
                GoogleCustomerConnection.workspace_id == policy.workspace_id
            )
        )
        assert native
        native.encrypted_grant = Vault().seal(policy.workspace_id, native.id, "offline-refresh")
        draft = db.scalar(
            select(CampaignDraft).where(CampaignDraft.workspace_id == policy.workspace_id)
        )
        assert draft
        draft_id, draft_revision = draft.id, draft.revision
        db.commit()
    selected = manifest()
    file = path / "execution-manifest.json"
    file.write_text(selected.model_dump_json())
    monkeypatch.setattr(settings, "google_execution_manifest_path", str(file))
    monkeypatch.setattr(settings, "google_execution_manifest_digest", selected.digest())
    monkeypatch.setattr(assembly, "execution_clock", lambda: NOW)
    descriptor = GoogleEvidenceDescriptor(
        source_id=selected.evidence_source_id,
        profile_digest=selected.evidence_profile_digest,
        environment="contract_test",
        kind="contract_scenario",
    )

    def build(sessions: Any, authorize: Any, actor_id: str, clock: Any) -> GoogleExecutionEvidence:
        def facts(db: Session, binding: Any, plan: Any, now: Any) -> PortfolioFacts:
            authorize(db, binding_scope := plan.review.scope.workspace_id, actor_id)
            _, current = execution_mandates.checked(db, binding_scope, binding, actor_id, clock)
            return PortfolioFacts(
                qualification_id="f" * 32,
                profile_id="explicit_google_scenario",
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
                budget_owner_key="new/google/" + plan.digest(),
                target_set_digest=plan.digest(),
                proposed_owner_upper_micros=plan.review.configuration.reservation_micros,
            )

        reader = PortfolioExposureReader(
            facts,
            {
                "explicit_google_scenario": QualificationProfile(
                    environment="contract_test",
                    model_version="explicit_fixture_only",
                    semantics="contract_scenario",
                    maximum_age_seconds=60,
                )
            },
            clock=clock,
        )
        return GoogleExecutionEvidence(descriptor, reader, reader.for_activation)

    registration = RegisteredGoogleEvidenceSource(descriptor, build)
    monkeypatch.setattr(
        assembly,
        "registered_google_evidence",
        lambda name: registration if name == descriptor.source_id else None,
    )
    rows = response_rows()
    rows["customer"].update(timeZone="Pacific/Pago_Pago", resourceName="customers/1234567890")
    rows["customConversionGoal"]["name"] = "Shop Purchases"
    rows["conversionAction"]["ownerCustomer"] = "customers/1234567890"
    server = Server()
    requests: list[httpx.Request] = []
    control: dict[str, Any] = {"transports_opened": 0, "transports_closed": 0}

    def wire(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        callback = control.pop("callback", None)
        if callback:
            callback()
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(
                200,
                json={"access_token": "offline-access", "expires_in": 3600, "token_type": "Bearer"},
            )
        if request.url.path.endswith("googleAds:search"):
            query = json.loads(request.content)["query"]
            table = query.split(" FROM ")[1].split()[0]
            key = table.split("_")[0] + "".join(p.title() for p in table.split("_")[1:])
            if key == "customer" and server.posts:
                qualification_callback = control.pop("qualification_callback", None)
                if qualification_callback:
                    qualification_callback()
            if key in rows:
                return httpx.Response(200, json={"results": [{key: rows[key]}]})
        return server(request)

    class TrackedTransport(httpx.MockTransport):
        def close(self) -> None:
            control["transports_closed"] += 1
            super().close()

    def transport(manifest: GoogleExecutionManifestV1) -> httpx.BaseTransport:
        control["transports_opened"] += 1
        return TrackedTransport(wire)

    monkeypatch.setattr(assembly, "google_execution_transport", transport)
    alice.app.include_router(router)
    login(alice, "configured-google:1")
    p = policy.model_dump(
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
    p["account_ids"] = [a.account.account_id for a in policy.accounts]
    return (
        alice,
        f"/api/customer/v1/workspaces/{policy.workspace_id}/execution",
        p,
        draft_id,
        draft_revision,
        server,
        requests,
        control,
    )
