"""Persisted approved source -> separate consent -> real mocked social HTTP graphs."""

from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount
from app.campaign_review import service as source
from app.campaign_review.contracts import RevisionInput
from app.campaign_review.storage import LocalMediaStore
from app.executors.google_publication import GooglePublicationHTTP
from app.executors.meta_publication import MetaPublicationTransport
from app.executors.tiktok_linked_publication import LinkedPushTikTokTransport
from app.executors.tiktok_publication import TikTokPublicationTransport
from app.mandates import service as simulation
from app.mandates.models import Mandate
from app.mandates.schemas import AccountScope
from app.meta.models import MetaConnection
from app.publication import coordinator as c
from app.publication import execution_mandates as mandates
from app.publication import tiktok_linked_review_service as linked_service
from app.publication.coordinator_contracts import (
    ConfigurationQualification,
    CreationPlan,
    CreationRuntime,
)
from app.publication.execution_authorization import owner_authorizer
from app.publication.execution_contracts import (
    ExecutionAccount,
    ExposureEvidence,
    ProviderMandateBinding,
)
from app.publication.execution_models import (
    ProviderExposureReservation,
)
from app.publication.scoped_media import ScopedProviderMediaReader
from app.publication.social_contracts import SocialProviderContext, SocialPublicationReview
from app.publication.tiktok_linked_plan import LinkedPushPublicationReviewV1, compile_linked_push
from app.settings import Settings
from app.sources.models import SourceConnection
from app.workspaces.models import WorkspaceIntegration
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tests.test_campaign_review import png
from tests.test_campaign_video import encoded as encoded
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_provider_execution_mandates import setup
from tests.test_shopify_sales import configuration as configuration
from tests.test_social_coordinator_journeys import SocialServer
from tests.test_social_publication_http import reviewed, tiktok_reviewed
from tests.test_tiktok_linked_plan import linked_review
from tests.test_tiktok_linked_review_contracts import document


def ready_linked(
    db: Session,
    config: Settings,
    path: Path,
    provider: str,
    video: bytes | None,
    server: SocialServer,
) -> tuple[int, str, str, LocalMediaStore, CreationRuntime, Any]:
    # Confirm the matching goal ceiling before constructing the social mandate.
    policy, actor = setup(db, config, path, goal_budget_micros=100_000_000)
    wid = policy.workspace_id
    old = db.scalar(select(Mandate).where(Mandate.workspace_id == wid))
    assert old is not None
    integration = WorkspaceIntegration(
        workspace_id=wid,
        integration_key="social-journey",
        provider=provider,
        display_name="Offline social",
        status="active",
        configuration={},
    )
    db.add(integration)
    db.flush()
    account = AdvertisingAccount(
        workspace_id=wid,
        connection_id=integration.id,
        platform=AdvertisingPlatform(provider),
        external_account_id="1234567890",
        name="Offline",
        currency_code="USD",
        time_zone="UTC",
    )
    db.add(account)
    db.flush()
    native: Any
    if provider == "meta_ads":
        native = MetaConnection(
            workspace_id=wid,
            workspace_integration_id=integration.id,
            account_id=account.id,
            external_account_id=account.external_account_id,
            encrypted_credentials="never-opened-offline",
        )
    else:
        native = SourceConnection(
            id=uuid4().hex,
            workspace_id=wid,
            integration_id=integration.id,
            account_id=account.id,
            provider=provider,
            external_id=account.external_account_id,
            status="connected",
            generation=1,
            window_start=NOW.date(),
            window_end=NOW.date(),
            staged={},
        )
    db.add(native)
    db.flush()
    scope = AccountScope(platform=provider, connection_id=integration.id, account_id=account.id)
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
    media = source.upload(db, wid, actor, video if video is not None else png(), store, NOW)
    cover = source.upload(db, wid, actor, png(), store, NOW)
    content = (
        reviewed() if provider == "meta_ads" else tiktok_reviewed()
    ).source.definition.content.model_dump()
    content["media"] = {"media_id": media.id, "sha256": media.sha256}
    body = RevisionInput(
        account=scope,
        mandate_id=old.id,
        mandate_revision=old.revision,
        currency="USD",
        budget_micros=40_000_000,
        starts_at=NOW,
        ends_at=NOW + timedelta(hours=1),
        content=content,
    )
    revision = source.revise(db, wid, body, actor, store, NOW)
    source.approve(
        db, wid, revision.draft_id, revision.revision, revision.digest, actor, store, NOW
    )
    _, artifact = source.preview(db, wid, revision.draft_id, store, NOW)
    media_reader = ScopedProviderMediaReader(db, store)
    fields = (
        reviewed() if provider == "meta_ads" else tiktok_reviewed()
    ).configuration.model_dump()
    fields["reservation_micros"] = 40_000_000
    if provider == "meta_ads":
        fields.update(
            adset_lifetime_budget_micros=40_000_000, image=media_reader.binding(wid, media.id)
        )
        server.media = {"image": fields["image"]}
    else:
        fields.update(
            lifetime_budget_micros=40_000_000,
            video=media_reader.binding(wid, media.id),
            cover=media_reader.binding(wid, cover.id),
        )
        server.media = {"video": fields["video"], "image": fields["cover"]}
    review = SocialPublicationReview(
        source=artifact,
        source_digest=artifact.fingerprint(),
        scope={
            "workspace_id": wid,
            "account": scope,
            "external_advertiser_id": account.external_account_id,
            "connection_version": artifact.connection_version,
            "mandate_id": old.id,
            "mandate_revision": old.revision,
        },
        configuration=fields,
        qualification_blockers=["live_profile_unqualified"],
    )
    linked = linked_review(review)
    configuration_document = document(linked)
    config_row = linked_service.prepare(
        db, wid, actor, configuration_document, lambda: NOW, owner_authorizer
    )
    config_approval = linked_service.confirm(
        db,
        wid,
        config_row.id,
        config_row.digest,
        actor,
        configuration_document,
        lambda: NOW,
        owner_authorizer,
    )
    linked = LinkedPushPublicationReviewV1.model_validate(
        {
            **linked.model_dump(),
            "configuration": configuration_document.configuration,
            "configuration_review": dict(
                review_id=config_row.id,
                review_digest=config_row.digest,
                approval_digest=config_approval.digest,
            ),
        }
    )
    plan = compile_linked_push(linked)
    policy = policy.model_copy(
        update={
            "accounts": [ExecutionAccount.from_publication(review.scope)],
            "total_cap_micros": 100_000_000,
            "per_plan_cap_micros": 80_000_000,
            "positive_change_cap_micros": 20_000_000,
        }
    )
    production = mandates.revise(db, wid, policy, actor, lambda: NOW)
    consent = mandates.consent(db, wid, production.id, 1, policy.digest(), actor, lambda: NOW)

    def qualify(p: CreationPlan, now: Any) -> ConfigurationQualification:
        assert p.digest() == plan.digest()
        return ConfigurationQualification(
            environment="contract_test",
            account=policy.accounts[0],
            plan_digest=p.digest(),
            api_version=p.api_version,
            observed_at=now,
            expires_at=now + timedelta(minutes=5),
            evidence_digest=p.digest(),
            checks_version="explicit_mock_http_scenario_not_live_v1",
            unresolved=[],
        )

    def exposure(
        session: Session, b: ProviderMandateBinding, p: CreationPlan, now: Any
    ) -> ExposureEvidence:
        held = (
            session.scalar(
                select(func.coalesce(func.sum(ProviderExposureReservation.amount_micros), 0)).where(
                    ProviderExposureReservation.workspace_id == wid,
                    ProviderExposureReservation.state == "held",
                )
            )
            or 0
        )
        held = int(held)  # PostgreSQL SUM(bigint) returns an exact Decimal.
        return ExposureEvidence(
            environment="contract_test",
            mandate=b,
            account=policy.accounts[0],
            covered_account_ids=[account.id],
            budget_owner_key="new/" + provider + "/" + p.digest(),
            target_set_digest=p.digest(),
            state_digest=p.digest(),
            currency="USD",
            period_start=policy.starts_at,
            period_end=policy.ends_at,
            observed_at=now,
            expires_at=now + timedelta(minutes=5),
            reporting_watermark=now,
            completeness="complete",
            qualification_id="f" * 32,
            model_version="explicit_contract_scenario_v1",
            cap_semantics="contract_scenario",
            reported_spend_micros=0,
            unreported_upper_micros=0,
            unchanged_future_upper_micros=0,
            proposed_owner_upper_micros=40_000_000,
            existing_reservations_micros=held,
            portfolio_upper_micros=held + 40_000_000,
        )

    def assert_current(doc: Any, now: Any) -> None:
        assert doc == configuration_document
        linked_service.current_capabilities(
            doc,
            doc.identity_observation.model_copy(
                update={"observed_at": now, "expires_at": now + timedelta(minutes=5)}
            ),
            doc.advertiser_observation.model_copy(
                update={"observed_at": now, "expires_at": now + timedelta(minutes=5)}
            ),
            now,
        )

    runtime = CreationRuntime(
        environment="contract_test",
        linked_tiktok=LinkedPushTikTokTransport(
            media_reader, transport=httpx.MockTransport(server)
        ),
        linked_context=lambda r: SocialProviderContext(
            scope=r.scope,
            access_token=SecretStr("offline-token"),
            expires_at=NOW + timedelta(hours=1),
        ),
        linked_configuration_current=lambda doc, now: assert_current(doc, now),
        qualification_reader=qualify,
        exposure_reader=exposure,
        google=GooglePublicationHTTP(
            transport=httpx.MockTransport(
                lambda r: (_ for _ in ()).throw(AssertionError("unexpected Google"))
            )
        ),
        meta=MetaPublicationTransport(media_reader, transport=httpx.MockTransport(server)),
        tiktok=TikTokPublicationTransport(media_reader, transport=httpx.MockTransport(server)),
        google_context=lambda r: (_ for _ in ()).throw(AssertionError("unexpected Google context")),
        social_context=lambda r: SocialProviderContext(
            scope=r.scope,
            access_token=SecretStr("offline-token"),
            expires_at=NOW + timedelta(hours=1),
        ),
    )
    row = c.prepare_creation(db, wid, plan, consent, actor, store, runtime, lambda: NOW)
    c.approve_creation(
        db, wid, row.id, row.digest, row.plan_digest, actor, store, runtime, lambda: NOW
    )
    run = c.create_run(db, wid, row.id, actor, store, runtime, lambda: NOW)
    return wid, run.id, actor, store, runtime, native
