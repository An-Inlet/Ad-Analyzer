"""Synthetic restore graph, built through real coordinators with no network transport.

Contract-scenario exposure/finality evidence below is NOT a native spending proof.
This module is used only by the disposable restore drill and its offline tests.
"""

import copy
import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx
from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount
from app.advertising_capabilities import AdvertisingWritesDisabled
from app.campaign_review.contracts import ReviewArtifact, RevisionInput
from app.campaign_review.models import CampaignDraft, CampaignRevision, MediaObject
from app.commerce.models import CommerceStore
from app.executors.google_optimization import GoogleOptimizationTransport
from app.goals import service as goals
from app.goals.models import Goal
from app.goals.schemas import ConfirmInput, GoalDefinition
from app.google_connections.models import GoogleCustomerConnection
from app.mandates.schemas import AccountScope
from app.publication import execution_mandates as mandates
from app.publication import optimization as o
from app.publication import replacement as r
from app.publication import social_review_service as social
from app.publication.contracts import fingerprint
from app.publication.execution_authorization import owner_authorizer
from app.publication.execution_contracts import (
    ExecutionAccount,
    ExposureEvidence,
    ProviderMandatePolicy,
)
from app.publication.execution_models import (
    ProviderExposureReservation,
)
from app.publication.optimization_contracts import (
    GoogleBudgetSetV1,
    MoneyContext,
    OptimizationContext,
    OptimizationTarget,
)
from app.publication.optimization_execution_contracts import (
    OptimizationQualification,
    OptimizationRuntime,
)
from app.publication.replacement_contracts import (
    ClosedOriginalRequest,
    ReplacementEvidence,
)
from app.publication.social_catalog import SocialCatalogRequest
from app.publication.social_contracts import MetaImagePublicationFields, ProviderMediaBinding
from app.publication.social_review_contracts import (
    MetaNoDSAAnswer,
    SocialConfigurationDocument,
    SocialRequirements,
)
from app.workspaces.models import WorkspaceIntegration
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

NOW = datetime(2026, 10, 6, tzinfo=UTC)
CUSTOMER = "1234567890"
BUDGET = f"customers/{CUSTOMER}/campaignBudgets/9"
CAMPAIGN = f"customers/{CUSTOMER}/campaigns/5"


class Server:
    def __init__(self) -> None:
        self.account: dict[str, Any] = {
            "id": CUSTOMER,
            "resourceName": f"customers/{CUSTOMER}",
            "status": "ENABLED",
            "currencyCode": "USD",
            "timeZone": "UTC",
        }
        self.campaign: dict[str, Any] = {
            "id": "5",
            "resourceName": CAMPAIGN,
            "campaignBudget": BUDGET,
            "status": "ENABLED",
            "primaryStatus": "ELIGIBLE",
            "advertisingChannelType": "SEARCH",
            "biddingStrategyType": "MANUAL_CPC",
            "networkSettings": {"targetGoogleSearch": True},
            "startDateTime": "2026-10-01 00:00:00",
            "endDateTime": "2026-10-31 23:59:59",
        }
        self.budget: dict[str, Any] = {
            "resourceName": BUDGET,
            "amountMicros": "50000000",
            "referenceCount": "1",
            "period": "DAILY",
            "deliveryMethod": "STANDARD",
            "status": "ENABLED",
            "type": "STANDARD",
        }
        self.calls: list[str] = []
        self.writes: list[dict[str, Any]] = []
        self.timeout = False
        self.ignore = False
        # Only synchronous completed mock requests enter this finality set.
        self.closed_requests: set[str] = set()

    def __call__(self, req: httpx.Request) -> httpx.Response:
        assert req.url.host == "googleads.googleapis.com"
        assert req.url.path.startswith(f"/v25/customers/{CUSTOMER}/")
        assert req.method == "POST" and not req.url.query
        body = json.loads(req.content)
        self.calls.append(req.url.path)
        if req.url.path.endswith(":mutate"):
            assert body["partialFailure"] is False and len(body["operations"]) == 1
            if body["validateOnly"]:
                return httpx.Response(200, json={})
            self.writes.append(body)
            op = body["operations"][0]
            assert req.url.path.endswith("campaignBudgets:mutate")
            assert op["updateMask"] == "amountMicros"
            assert set(op["update"]) == {"resourceName", "amountMicros"}
            if not self.ignore:
                self.budget.update(op["update"])
            if self.timeout:
                raise httpx.ReadTimeout("synthetic unknown outcome")
            return httpx.Response(200, json={"results": [{"resourceName": BUDGET}]})
        query = body["query"]
        if "FROM customer" in query:
            rows = [{"customer": self.account}]
        elif "FROM campaign_budget" in query:
            rows = [{"campaignBudget": self.budget}]
        elif "FROM recommendation_subscription" in query:
            rows = []
        elif "WHERE campaign.id" in query:
            rows = [{"campaign": self.campaign}]
        else:
            assert "campaign.campaign_budget = '" + BUDGET + "'" in query
            rows = [{"campaign": self.campaign}]
        return httpx.Response(200, json={"results": copy.deepcopy(rows)})


def reader(runtime: Any, server: Server) -> Any:
    def qualify(db, binding, intent, before, qualification, snapshot, now):  # type: ignore[no-untyped-def]
        assert snapshot.receipts
        assert all(x.request_digest in server.closed_requests for x in snapshot.receipts)
        raw = runtime.exposure_reader(db, intent, before, qualification, now).model_dump()
        raw["existing_reservations_micros"] -= snapshot.ancestry[-1].amount_micros
        raw["portfolio_upper_micros"] -= snapshot.ancestry[-1].amount_micros
        return ReplacementEvidence(
            snapshot_digest=snapshot.digest(),
            intent_digest=intent.digest(),
            environment="contract_test",
            qualification_profile="mock_complete_transition",
            qualification_revision=1,
            proof_kind="contract_scenario",
            observed_at=now,
            expires_at=now + timedelta(minutes=2),
            closed_requests=[
                ClosedOriginalRequest(
                    attempt_id=x.attempt_id,
                    request_digest=x.request_digest,
                    fence=x.fence,
                    basis="authoritative_request_terminal",
                    evidence_digest="a" * 64,
                )
                for x in snapshot.receipts
            ],
            closure_evidence_digest="b" * 64,
            transition_evidence_digest="c" * 64,
            transition_semantics="current_proposed_delayed_no_effect_and_residual",
            portfolio=ExposureEvidence.model_validate(raw),
            unresolved=[],
        )

    return qualify


def runtime_for(policy: ProviderMandatePolicy, server: Server) -> OptimizationRuntime:
    scope = policy.accounts[0]
    adapter = GoogleOptimizationTransport(transport=httpx.MockTransport(server))
    money = MoneyContext(
        currency="USD",
        currency_exponent=2,
        account_timezone="UTC",
        period_start=policy.starts_at,
        period_end=policy.ends_at,
    )

    def context(scope: ExecutionAccount) -> OptimizationContext:
        return OptimizationContext(
            scope=scope,
            access_token=SecretStr("offline-token"),
            expires_at=NOW + timedelta(hours=1),
        )

    def qualify(
        db: Session,
        binding: Any,
        scope: ExecutionAccount,
        target: OptimizationTarget,
        now: datetime,
    ) -> OptimizationQualification:
        return OptimizationQualification(
            environment="contract_test",
            scope=scope,
            target=target,
            money=money,
            qualification_id="e" * 32,
            qualification_revision=1,
            profile="synthetic_restore_only",
            allowed_operations=["google_budget_set_v1"],
            observed_at=now,
            expires_at=now + timedelta(minutes=2),
            evidence_digest="f" * 64,
            unresolved=[],
        )

    def exposure(
        db: Session, intent: Any, state: Any, qualification: Any, now: datetime
    ) -> ExposureEvidence:
        held = int(
            db.scalar(
                select(func.coalesce(func.sum(ProviderExposureReservation.amount_micros), 0)).where(
                    ProviderExposureReservation.workspace_id == scope.workspace_id,
                    ProviderExposureReservation.state == "held",
                )
            )
            or 0
        )
        return ExposureEvidence(
            environment="contract_test",
            mandate=intent.mandate,
            account=scope,
            covered_account_ids=[scope.account.account_id],
            budget_owner_key=intent.budget_owner.key(scope),
            target_set_digest=intent.approved_target_set_digest,
            state_digest=state.digest(),
            currency="USD",
            period_start=policy.starts_at,
            period_end=policy.ends_at,
            observed_at=now,
            expires_at=now + timedelta(minutes=2),
            reporting_watermark=now,
            completeness="complete",
            qualification_id=qualification.qualification_id,
            model_version="synthetic_restore_only",
            cap_semantics="contract_scenario",
            reported_spend_micros=1_000_000,
            unreported_upper_micros=0,
            unchanged_future_upper_micros=0,
            proposed_owner_upper_micros=40_000_000,
            existing_reservations_micros=held,
            portfolio_upper_micros=held + 41_000_000,
        )

    runtime = OptimizationRuntime(
        environment="contract_test",
        qualification_reader=qualify,
        exposure_reader=exposure,
        context=context,
        google=adapter,
    )
    return replace(runtime, replacement_reader=reader(runtime, server))


def seed_financial(engine: Engine) -> None:
    """A complete zero-sales fixture baseline; service-created exact consents and lineage."""
    with Session(engine) as db:
        wid, actor = 901, "1" * 32
        commerce = WorkspaceIntegration(
            workspace_id=wid,
            integration_key="restore-shopify",
            provider="shopify",
            display_name="Synthetic",
            status="active",
            configuration={},
        )
        google = WorkspaceIntegration(
            workspace_id=wid,
            integration_key="restore-google",
            provider="google_ads",
            display_name="Synthetic",
            status="active",
            configuration={},
        )
        db.add_all([commerce, google])
        db.flush()
        store = CommerceStore(
            id=uuid4().hex,
            workspace_id=wid,
            connection_id=commerce.id,
            shop_key="a" * 64,
            shop_domain="restore-fixture.myshopify.com",
            currency="USD",
            time_zone="UTC",
            connected_at=NOW,
            covered_from=NOW - timedelta(days=60),
            last_sync_at=NOW,
        )
        db.add(store)
        db.flush()
        goal = Goal(id=uuid4().hex, workspace_id=wid, revision=0)
        db.add(goal)
        db.flush()
        definition = GoalDefinition(
            metric="shopify_merchandise_net_sales_v1",
            store_id=store.id,
            target_micros=100_000_000,
            target_window=dict(
                start="2026-11-01",
                end="2026-12-01",
                time_basis="calendar_month",
                currency="USD",
                time_zone="UTC",
            ),
            baseline_window=dict(
                start="2026-09-01",
                end="2026-10-01",
                time_basis="calendar_month",
                currency="USD",
                time_zone="UTC",
            ),
            deadline=date(2026, 11, 30),
            budget_micros=100_000_000,
            budget_start=date(2026, 11, 1),
            budget_end=date(2026, 12, 1),
            aggressiveness="balanced",
        )
        goals.revise(db, goal, definition, actor, NOW)
        preview = goals.preview(db, goal, NOW)
        goals.confirm(
            db,
            goal,
            ConfirmInput(
                expected_revision=goal.revision,
                preview_id=preview.id,
                idempotency_key="restore-confirm",
            ),
            NOW,
            actor_id=actor,
        )
        account = AdvertisingAccount(
            workspace_id=wid,
            connection_id=google.id,
            platform=AdvertisingPlatform.GOOGLE_ADS,
            external_account_id=CUSTOMER,
            name="Synthetic",
            currency_code="USD",
            time_zone="UTC",
        )
        db.add(account)
        db.flush()
        native = GoogleCustomerConnection(
            id=uuid4().hex,
            workspace_id=wid,
            integration_id=google.id,
            account_id=account.id,
            external_account_id=CUSTOMER,
            encrypted_grant=None,
            generation=1,
            status="connected",
            backfill_through=NOW.date(),
            history_floor=NOW.date() - timedelta(days=90),
            window_start=NOW.date(),
            window_end=NOW.date(),
            staged={},
        )
        db.add(native)
        db.flush()
        scope = ExecutionAccount(
            workspace_id=wid,
            account=AccountScope(
                platform="google_ads", connection_id=google.id, account_id=account.id
            ),
            external_advertiser_id=CUSTOMER,
            connection_version=f"google:{native.id}:1",
        )
        policy = ProviderMandatePolicy(
            environment="contract_test",
            workspace_id=wid,
            goal_id=goal.id,
            goal_revision=goal.revision,
            currency="USD",
            time_zone="UTC",
            starts_at=NOW - timedelta(hours=1),
            ends_at=NOW + timedelta(hours=23),
            accounts=[scope],
            total_cap_micros=100_000_000,
            per_plan_cap_micros=80_000_000,
            positive_change_cap_micros=20_000_000,
            action_limit=10,
            cooldown_seconds=0,
            freshness_seconds=300,
            aggressiveness_percent=5,
            allowed_purposes=["existing_campaign_optimize"],
            allowed_target_set_digest="0" * 64,
            campaign_and_creative_policy="new_exact_review_required",
            activation_policy="separate_exact_approval",
        )
        server = Server()
        runtime = runtime_for(policy, server)
        target = OptimizationTarget(kind="campaign", external_id="5", campaign_id="5")
        qualification = runtime.qualification_reader(db, None, scope, target, NOW)  # type: ignore[arg-type]
        before = runtime.transport(scope).read_current(
            scope, target, qualification.money, "e" * 32, 1, runtime.context(scope), NOW
        )
        policy = policy.model_copy(
            update={"allowed_target_set_digest": before.budget_owner.target_set_digest()}
        )
        runtime = runtime_for(policy, server)
        db.commit()
        mandate = mandates.revise(db, wid, policy, actor, lambda: NOW)
        binding = mandates.consent(
            db, wid, mandate.id, mandate.revision, policy.digest(), actor, lambda: NOW
        )
        # Positive changes prove cumulative nonrefundable charges survive restore.
        original = o.prepare_optimization(
            db,
            wid,
            binding,
            scope,
            target,
            GoogleBudgetSetV1(amount_micros=51_000_000),
            "a" * 64,
            actor,
            runtime,
            lambda: NOW,
        )
        o.approve_optimization(
            db, wid, original.id, original.digest, original.plan_digest, actor, runtime, lambda: NOW
        )
        old = o.create_run(db, wid, original.id, actor, runtime, lambda: NOW)
        claim = o.claim_step(db, wid, old.id, actor, runtime, lambda: NOW)
        assert claim is not None
        assert (
            o.execute_claim(db, claim, actor, runtime, lambda: NOW).outcome
            == "verified_target_state"
        )
        # Mock transport has completed synchronously, with no deferred operation.
        # This explicit fixture terminal fact is separate from observed target state.
        server.closed_requests.add(claim.request.digest())
        assert old.reservation_id is not None
        review = r.prepare_repeat_optimization(
            db,
            wid,
            binding,
            scope,
            old.reservation_id,
            target,
            GoogleBudgetSetV1(amount_micros=52_000_000),
            "b" * 64,
            actor,
            runtime,
            lambda: NOW,
        )
        o.approve_optimization(
            db, wid, review.id, review.digest, review.plan_digest, actor, runtime, lambda: NOW
        )
        successor = o.create_run(db, wid, review.id, actor, runtime, lambda: NOW)
        claim = o.claim_step(db, wid, successor.id, actor, runtime, lambda: NOW)
        assert claim is not None
        server.ignore = server.timeout = True
        assert o.execute_claim(db, claim, actor, runtime, lambda: NOW).outcome == "unknown"
        assert len(server.writes) == 2
        db.commit()


def image() -> ProviderMediaBinding:
    return ProviderMediaBinding(
        media_id="e" * 32,
        sha256="f" * 64,
        byte_size=100,
        mime="image/png",
        width=100,
        height=100,
        validation_version="image_v1",
        validation_digest="a" * 64,
    )


def meta_fields() -> MetaImagePublicationFields:
    return MetaImagePublicationFields(
        kind="meta_image_v26",
        account_timezone="UTC",
        currency="USD",
        currency_minor_unit_exponent=2,
        reservation_micros=200_000_000,
        adset_lifetime_budget_micros=200_000_000,
        budget_semantics="lifetime_budget_not_independent_hard_cap",
        activation_policy="separate_exact_approval",
        automation_omission_policy="no_optional_assets_or_automation_requested",
        page_id="100",
        pixel_id="101",
        conversion_event="PURCHASE",
        objective="OUTCOME_SALES",
        buying_type="AUCTION",
        bid_strategy="LOWEST_COST_WITHOUT_CAP",
        optimization_goal="OFFSITE_CONVERSIONS",
        billing_event="IMPRESSIONS",
        destination_type="WEBSITE",
        attribution=[{"event_type": "CLICK_THROUGH", "window_days": 7}],
        attribution_count_type="ALL_CONVERSIONS",
        countries=["US"],
        language_locale_ids={"en": 1001},
        age_min=18,
        age_max=65,
        publisher_platforms=["facebook"],
        facebook_positions=["feed"],
        advantage_audience=0,
        dynamic_creative=False,
        is_adset_budget_sharing_enabled=False,
        special_ad_categories=[],
        special_ad_category_declaration="none_applicable",
        dsa_beneficiary=None,
        dsa_payor=None,
        url_tags="",
        image=image(),
    )


def seed_social(engine: Engine) -> None:
    """Restore exact typed metadata/approval; this does not qualify media-object recovery."""
    with Session(engine) as db:
        wid, actor = 902, "2" * 32
        integration = WorkspaceIntegration(
            workspace_id=wid,
            integration_key="restore-meta",
            provider="meta_ads",
            display_name="Synthetic",
            status="active",
            configuration={},
        )
        db.add(integration)
        db.flush()
        account = AdvertisingAccount(
            workspace_id=wid,
            connection_id=integration.id,
            platform=AdvertisingPlatform.META_ADS,
            external_account_id="123",
            name="Synthetic",
            currency_code="USD",
            time_zone="UTC",
        )
        db.add(account)
        db.flush()
        scope = ExecutionAccount(
            workspace_id=wid,
            account=AccountScope(
                platform="meta_ads", connection_id=integration.id, account_id=account.id
            ),
            external_advertiser_id="123",
            connection_version="meta:synthetic:1",
        )
        draft = CampaignDraft(id=uuid4().hex, workspace_id=wid, revision=1)
        db.add(draft)
        db.flush()
        media = image()
        artifact = ReviewArtifact(
            draft_id=draft.id,
            revision=1,
            workspace_id=wid,
            connection_version=scope.connection_version,
            definition=RevisionInput(
                account=scope.account,
                mandate_id="a" * 32,
                mandate_revision=1,
                currency="USD",
                budget_micros=200_000_000,
                starts_at=NOW,
                ends_at=NOW + timedelta(days=1),
                content=dict(
                    kind="meta_website_sales_image_v1",
                    objective="website_sales",
                    name="Synthetic review",
                    landing_page="https://example.invalid/product",
                    audience=dict(countries=["US"], languages=["en"]),
                    headline="Synthetic headline",
                    text="Synthetic supplied copy",
                    call_to_action="SHOP_NOW",
                    media=dict(media_id=media.media_id, sha256=media.sha256),
                ),
            ),
            media=[dict(media_id=media.media_id, sha256=media.sha256)],
            offline_reviewable=True,
            blockers=[],
        )
        db.add(
            CampaignRevision(
                draft_id=draft.id,
                revision=1,
                workspace_id=wid,
                artifact=artifact.model_dump(mode="json"),
                digest=artifact.fingerprint(),
                created_by=actor,
                created_at=NOW,
                approved_by=actor,
                approved_at=NOW,
            )
        )
        db.add(
            MediaObject(
                id=media.media_id,
                workspace_id=wid,
                sha256=media.sha256,
                size=media.byte_size,
                mime=media.mime,
                width=media.width,
                height=media.height,
                created_by=actor,
                created_at=NOW,
            )
        )
        db.flush()
        fields = meta_fields()
        document = SocialConfigurationDocument(
            request=SocialCatalogRequest(
                account=scope,
                draft_id=draft.id,
                draft_revision=1,
                source_digest=artifact.fingerprint(),
                countries=["US"],
                languages=["en"],
                content_kind="meta_website_sales_image_v1",
            ),
            environment="contract_test",
            option_id="b" * 64,
            requirements=SocialRequirements(
                profile_digest="c" * 64,
                requirements_digest="d" * 64,
                wording_version="restore-contract-v1",
                verified=True,
                dsa_required=False,
                wording="Synthetic restore review: no special category; no DSA declaration.",
            ),
            primary=media,
            cover=None,
            answer=MetaNoDSAAnswer(special_category_answer="none_applicable"),
            configuration=fields,
            configuration_digest=fingerprint(
                "inlet.social-configuration-fields.v1", fields.model_dump(mode="json")
            ),
        )
        review = social.prepare(db, wid, actor, document, lambda: NOW, owner_authorizer)
        social.confirm(
            db, wid, review.id, review.digest, actor, document, lambda: NOW, owner_authorizer
        )
        db.commit()


def verify_populated(engine: Engine) -> None:
    """Exercise restored application behavior using available offline adapters, not a 503 gate."""
    from app.lifecycle.contracts import LifecycleScopeV1
    from app.lifecycle.export_serializers import serialize
    from app.lifecycle.inventory import export_section
    from app.publication import coordinator, settlement
    from app.publication.execution_models import (
        ProviderExecutionAttempt,
        ProviderExecutionReview,
        ProviderExecutionRun,
        ProviderReservationReplacement,
    )
    from app.publication.optimization_contracts import OptimizationRequest
    from app.publication.optimization_execution_contracts import OptimizationClaim
    from app.publication.replacement_contracts import (
        RepeatOptimizationReview,
        ReplacementAuditDocument,
    )
    from app.publication.social_review_models import SocialConfigurationReview

    with Session(engine) as db:
        audit = db.scalars(select(ProviderReservationReplacement)).one()
        document = ReplacementAuditDocument.model_validate(audit.document)
        assert document.digest() == audit.digest
        assert (
            document.predecessor_id,
            document.successor_id,
            document.successor_run_id,
            document.review_id,
        ) == (audit.predecessor_id, audit.successor_id, audit.successor_run_id, audit.review_id)
        predecessor = db.get(ProviderExposureReservation, audit.predecessor_id)
        successor = db.get(ProviderExposureReservation, audit.successor_id)
        assert predecessor is not None and successor is not None
        assert (predecessor.state, successor.state) == ("superseded", "held")
        assert predecessor.amount_micros == successor.amount_micros == 40_000_000
        assert successor.settled_evidence is None
        assert len(document.evidence.closed_requests) == 1
        assert document.snapshot.receipts[0].outcome == "verified_target_state"
        run = db.get(ProviderExecutionRun, audit.successor_run_id)
        review = db.get(ProviderExecutionReview, audit.review_id)
        assert run is not None and review is not None and run.reservation_id == successor.id
        repeat = RepeatOptimizationReview.model_validate(review.document)
        assert repeat.digest() == review.digest and repeat.plan.digest() == review.plan_digest
        attempt = db.scalars(
            select(ProviderExecutionAttempt).where(ProviderExecutionAttempt.run_id == run.id)
        ).one()
        request = OptimizationRequest.model_validate(attempt.request)
        assert request.digest() == attempt.request_digest
        ledger, mandate = mandates.owned(db, 901, repeat.plan.intent.mandate.mandate_id)
        policy = mandates.policy(db, mandate)
        assert ledger.action_count == 2 and ledger.spent_high_water_micros == 1_000_000
        assert o.positive_changes_used(db, 901, ledger.id) == 2_000_000
        receipt = coordinator.read_owned_outcome_receipt(db, 901, attempt.id, "1" * 32)
        assert receipt is not None and receipt.outcome == "unknown"
        server = Server()
        server.budget["amountMicros"] = "51000000"
        runtime = runtime_for(policy, server)
        before_counts = tuple(db.scalar(select(func.count()).select_from(model)) for model in (
            ProviderExecutionAttempt, ProviderExecutionRun, ProviderExposureReservation,
            ProviderReservationReplacement,
        ))
        try:
            o.claim_step(db, 901, run.id, "1" * 32, runtime, lambda: NOW)
        except AdvertisingWritesDisabled:
            pass
        else:
            raise AssertionError("planning restore claimed historical execution")
        claim = OptimizationClaim(
            workspace_id=901,
            run_id=run.id,
            attempt_id=attempt.id,
            environment="contract_test",
            request=request,
        )
        try:
            o.execute_claim(db, claim, "1" * 32, runtime, lambda: NOW)
        except AdvertisingWritesDisabled:
            pass
        else:
            raise AssertionError("restored unknown attempt replayed")
        try:
            r.prepare_repeat_optimization(
                db,
                901,
                repeat.plan.intent.mandate,
                repeat.plan.intent.scope,
                successor.id,
                repeat.plan.intent.target,
                GoogleBudgetSetV1(amount_micros=53_000_000),
                "c" * 64,
                "1" * 32,
                runtime,
                lambda: NOW,
            )
        except AdvertisingWritesDisabled:
            pass
        else:
            raise AssertionError("restored unknown outcome replaced")
        assert tuple(db.scalar(select(func.count()).select_from(model)) for model in (
            ProviderExecutionAttempt, ProviderExecutionRun, ProviderExposureReservation,
            ProviderReservationReplacement,
        )) == before_counts
        try:
            settlement.settle_unemitted(db, 901, successor.id, "1" * 32, lambda: NOW)
        except HTTPException as error:
            assert error.status_code == 409
            db.rollback()
        else:
            raise AssertionError("restored emitted hold refunded")
        assert not server.writes and not server.calls
        try:
            coordinator.read_owned_outcome_receipt(db, 902, attempt.id, "2" * 32)
        except HTTPException as error:
            assert error.status_code == 404
            db.rollback()
        else:
            raise AssertionError("restored foreign receipt visible")
        social_row = db.scalars(select(SocialConfigurationReview)).one()
        social_doc = SocialConfigurationDocument.model_validate(social_row.document)
        approval = social.read_confirmed(
            db, 902, social_row.id, social_row.digest, "2" * 32, social_doc, owner_authorizer
        )
        assert approval.review_digest == social_doc.digest()
        source = db.get(CampaignRevision, (social_row.draft_id, social_row.source_revision))
        assert source is not None
        artifact = ReviewArtifact.model_validate(source.artifact)
        assert artifact.fingerprint() == source.digest == social_doc.request.source_digest
        try:
            social.read_confirmed(
                db, 901, social_row.id, social_row.digest, "1" * 32, social_doc, owner_authorizer
            )
        except HTTPException as error:
            assert error.status_code == 404
            db.rollback()
        else:
            raise AssertionError("restored foreign configuration visible")
        for record, wid in ((audit, 901), (social_row, 902)):
            raw = {column.name: getattr(record, column.name) for column in record.__table__.columns}
            exported, missing = serialize(record.__tablename__, raw)
            assert not missing and exported["document"] == record.document
            _, missing = serialize(record.__tablename__, {**raw, "workspace_id": 1803 - wid})
            assert "document" in missing
            assert (
                len(
                    export_section(db, LifecycleScopeV1(workspace_id=wid), record.__tablename__)[
                        "rows"
                    ]
                )
                == 1
            )
            assert (
                export_section(db, LifecycleScopeV1(workspace_id=1803 - wid), record.__tablename__)[
                    "rows"
                ]
                == []
            )
        db.refresh(successor)
        db.refresh(ledger)
        assert successor.state == "held" and successor.amount_micros == 40_000_000
        assert ledger.action_count == 2 and ledger.spent_high_water_micros == 1_000_000
        assert o.positive_changes_used(db, 901, ledger.id) == 2_000_000
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 2


def verify_owned_constraints(engine: Engine) -> None:
    """Existing foreign workspace/account rows cannot be substituted in recovered graphs."""
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    statements = [
        "UPDATE provider_reservation_replacements SET workspace_id=902",
        "UPDATE customer_social_configuration_approvals SET workspace_id=901",
        "UPDATE customer_social_configuration_reviews SET account_id="
        "(SELECT id FROM advertising_accounts WHERE workspace_id=901)",
    ]
    for statement in statements:
        with engine.connect() as db:
            transaction = db.begin()
            try:
                db.execute(text(statement))
            except IntegrityError:
                transaction.rollback()
            else:
                transaction.rollback()
                raise AssertionError("restored financial or social ownership constraint missing")


def seed_performance(engine: Engine) -> None:
    """Synthetic staged source facts; execute the real terminal Meta publisher, no HTTP."""
    from decimal import Decimal

    from app.ads.models import Campaign
    from app.meta.models import MetaConnection, MetaStagedMetric
    from app.meta.sync import MetaSyncService
    from app.settings import Settings

    with Session(engine) as db:
        owner_authorizer(db, 902, "2" * 32)
        account = db.scalars(
            select(AdvertisingAccount).where(AdvertisingAccount.workspace_id == 902)
        ).one()
        source = MetaConnection(
            workspace_id=902,
            workspace_integration_id=account.connection_id,
            account_id=account.id,
            external_account_id=account.external_account_id,
            encrypted_credentials="synthetic-unusable",
            conversion_action_type="purchase",
            window_start=NOW.date(),
            window_end=NOW.date(),
            phase="insights",
        )
        campaign = Campaign(
            account_id=account.id,
            platform=AdvertisingPlatform.META_ADS,
            external_campaign_id="456",
            name="Synthetic reported campaign",
        )
        db.add_all([source, campaign])
        db.flush()
        db.add(
            MetaStagedMetric(
                connection_id=source.id,
                campaign_id=campaign.id,
                metric_date=NOW.date(),
                impressions=1000,
                clicks=100,
                cost_micros=100_000_000,
                conversions=Decimal("10"),
                conversion_value_micros=250_000_000,
            )
        )
        db.flush()
        assert MetaSyncService(db, Settings())._publish(source, NOW) == 1
        db.commit()


def verify_performance(engine: Engine) -> None:
    from app.ads.models import Campaign
    from app.campaign_performance import service
    from app.campaign_performance.models import CurrentPerformance, PerformanceCompletion
    from app.lifecycle.contracts import LifecycleScopeV1
    from app.lifecycle.inventory import export_section

    with Session(engine) as db:
        completion = db.scalars(select(PerformanceCompletion)).one()
        current = db.scalars(select(CurrentPerformance)).one()
        campaign = db.scalars(
            select(Campaign).where(Campaign.account_id == completion.account_id)
        ).one()
        assert current.completion_id == completion.id and current.workspace_id == 902
        result = service.read_current(
            db,
            902,
            "2" * 32,
            completion.account_id,
            campaign.id,
            completion.id,
            owner_authorizer,
        )
        assert result.spend_micros == 100_000_000 and result.conversions == "10.000000"
        assert result.conversion_value_micros == 250_000_000
        assert result.reported_day_count == 1 and completion.row_count == 1
        assert result.maturity == "unqualified" and not result.spending_authorized
        for table in ("campaign_performance_completions", "campaign_performance_current"):
            assert len(export_section(db, LifecycleScopeV1(workspace_id=902), table)["rows"]) == 1
            assert export_section(db, LifecycleScopeV1(workspace_id=901), table)["rows"] == []
        try:
            service.read_current(
                db,
                901,
                "1" * 32,
                completion.account_id,
                campaign.id,
                completion.id,
                owner_authorizer,
            )
        except HTTPException as error:
            assert error.status_code == 409
        else:
            raise AssertionError("restored foreign performance visible")


def verify_performance_constraints(engine: Engine) -> None:
    """Real migrated database only: immutable trigger and cascading privacy erasure."""
    from sqlalchemy import MetaData, Table, text
    from sqlalchemy.exc import DBAPIError, IntegrityError

    for statement in (
        "UPDATE campaign_performance_completions SET row_count=row_count",
        "UPDATE campaign_performance_current SET workspace_id=901",
        "UPDATE campaign_performance_current SET account_id="
        "(SELECT id FROM advertising_accounts WHERE workspace_id=901)",
        "INSERT INTO campaign_performance_completions SELECT "
        "* FROM campaign_performance_completions",  # Original receipt cannot be overwritten.
    ):
        with engine.connect() as db:
            transaction = db.begin()
            try:
                db.execute(text(statement))
            except DBAPIError:
                transaction.rollback()
            else:
                transaction.rollback()
                raise AssertionError("restored performance immutability or ownership missing")
    with engine.connect() as db:
        transaction = db.begin()
        table = Table("campaign_performance_completions", MetaData(), autoload_with=db)
        original = dict(db.execute(select(table)).mappings().one())
        try:
            db.execute(table.insert().values(**{**original, "id": "f" * 32, "workspace_id": 901}))
        except IntegrityError:
            transaction.rollback()
        else:
            transaction.rollback()
            raise AssertionError("restored completion/account composite ownership missing")
    with engine.connect() as db:
        transaction = db.begin()
        db.execute(text("DELETE FROM campaign_performance_completions"))
        assert db.scalar(text("SELECT count(*) FROM campaign_performance_current")) == 0
        transaction.rollback()
