"""Resolve customer choices into owned policy/review records; never trust provider proof."""

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount
from app.campaign_review import service as source_reviews
from app.campaign_review.contracts import MediaStore
from app.collectors.google_catalog import GoogleCatalogUnavailable
from app.google_connections.models import GoogleCustomerConnection
from app.mandates.schemas import AccountScope
from app.meta.models import MetaConnection
from app.publication import execution_mandates as mandates
from app.publication.customer_catalog import (
    GoogleCatalog,
    GoogleCatalogOption,
    GoogleCatalogRequest,
)
from app.publication.customer_runtime import CustomerExecutionRuntime
from app.publication.customer_schemas import (
    CreationIntent,
    GoogleTotalConfigurationIntent,
    PolicyIntent,
)
from app.publication.execution_contracts import (
    ExecutionAccount,
    ProviderMandateBinding,
    ProviderMandatePolicy,
)
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionConsent,
    ProviderExecutionMandate,
    ProviderExecutionReview,
    ProviderExecutionRun,
    ProviderExecutionStep,
    ProviderExposureReservation,
)
from app.publication.provider_contracts import (
    GooglePublicationFields,
    GoogleSearchPublicationFields,
    GoogleSearchTotalPublicationFields,
)
from app.sources.models import SourceConnection


def unavailable(code: str = "provider_execution_not_configured") -> HTTPException:
    return HTTPException(409, {"code": code, "message": "Provider execution is unavailable."})


def require_runtime(runtime: CustomerExecutionRuntime | None) -> CustomerExecutionRuntime:
    if runtime is None:
        raise unavailable()
    if runtime.creation.environment == "live" and not runtime.creation.live_enabled:
        raise unavailable()
    return runtime


def account(db: Session, wid: int, identifier: int) -> ExecutionAccount:
    row = db.scalar(
        select(AdvertisingAccount).where(
            AdvertisingAccount.id == identifier, AdvertisingAccount.workspace_id == wid
        )
    )
    if row is None or row.connection_id is None:
        raise HTTPException(404, "advertising account unavailable")
    platform = row.platform.value
    if platform == "google_ads":
        native = db.scalar(
            select(GoogleCustomerConnection).where(
                GoogleCustomerConnection.workspace_id == wid,
                GoogleCustomerConnection.account_id == identifier,
                GoogleCustomerConnection.integration_id == row.connection_id,
            )
        )
        version = f"google:{native.id}:{native.generation}" if native else ""
    elif platform == "meta_ads":
        meta = db.scalar(
            select(MetaConnection).where(
                MetaConnection.workspace_id == wid,
                MetaConnection.account_id == identifier,
                MetaConnection.workspace_integration_id == row.connection_id,
            )
        )
        version = f"meta:{meta.id}:{meta.generation}" if meta else ""
    else:
        source = db.scalar(
            select(SourceConnection).where(
                SourceConnection.workspace_id == wid,
                SourceConnection.account_id == identifier,
                SourceConnection.integration_id == row.connection_id,
                SourceConnection.provider == "tiktok_ads",
            )
        )
        version = f"tiktok:{source.id}:{source.generation}" if source else ""
    if not version:
        raise unavailable("current_account_connection_unavailable")
    scope = ExecutionAccount(
        workspace_id=wid,
        account=AccountScope(account_id=row.id, connection_id=row.connection_id, platform=platform),
        external_advertiser_id=row.external_account_id,
        connection_version=version,
    )
    mandates.current_account(db, scope)
    return scope


def policy(
    db: Session, wid: int, body: PolicyIntent, runtime: CustomerExecutionRuntime
) -> ProviderMandatePolicy:
    return ProviderMandatePolicy(
        **body.model_dump(exclude={"account_ids"}),
        workspace_id=wid,
        environment=runtime.creation.environment,
        accounts=[account(db, wid, i) for i in sorted(body.account_ids)],
        freshness_seconds=60,
        campaign_and_creative_policy="new_exact_review_required",
        activation_policy="separate_exact_approval",
    )


def binding(db: Session, wid: int, identifier: str, revision: int) -> ProviderMandateBinding:
    ledger, row = mandates.owned(db, wid, identifier)
    p = mandates.policy(db, row)
    consent = db.scalar(
        select(ProviderExecutionConsent).where(
            ProviderExecutionConsent.workspace_id == wid,
            ProviderExecutionConsent.mandate_id == row.id,
            ProviderExecutionConsent.revision == revision,
        )
    )
    if (
        row.revision != revision
        or row.state != "active"
        or consent is None
        or consent.policy_digest != p.digest()
    ):
        raise unavailable("separate_execution_consent_required")
    return ProviderMandateBinding(
        mandate_id=row.id,
        revision=revision,
        consent_id=consent.id,
        policy_digest=p.digest(),
        ledger_id=ledger.id,
        environment=p.environment,
    )


def policy_view(db: Session, row: ProviderExecutionMandate) -> dict[str, Any]:
    p = mandates.policy(db, row)
    return {
        "id": row.id,
        "revision": row.revision,
        "state": row.state,
        "policy_digest": p.digest(),
        "policy": p.model_dump(mode="json"),
        "consent_is_separate": True,
        "account_names": list(
            db.scalars(
                select(AdvertisingAccount.name)
                .where(
                    AdvertisingAccount.workspace_id == row.workspace_id,
                    AdvertisingAccount.id.in_([a.account.account_id for a in p.accounts]),
                )
                .order_by(AdvertisingAccount.id)
            )
        ),
        "account_set_locked_after_consent": True,
    }


def google_fields(
    db: Session,
    wid: int,
    body: CreationIntent,
    actor: str,
    media: MediaStore,
    runtime: CustomerExecutionRuntime,
    option: GoogleCatalogOption,
) -> GooglePublicationFields:
    draft, artifact = source_reviews.preview(db, wid, body.draft_id, media, runtime.clock())
    if draft.revision != body.draft_revision or draft.approved_by is None:
        raise unavailable("current_approved_creative_required")
    definition = artifact.definition
    if definition.account.platform != "google_ads":
        raise unavailable("provider_configuration_producer_unavailable")
    scope = account(db, wid, definition.account.account_id)
    native = db.scalar(
        select(GoogleCustomerConnection).where(
            GoogleCustomerConnection.workspace_id == wid,
            GoogleCustomerConnection.account_id == scope.account.account_id,
            GoogleCustomerConnection.integration_id == scope.account.connection_id,
        )
    )
    row = db.get(AdvertisingAccount, scope.account.account_id)
    if native is None or row is None or row.time_zone is None:
        raise unavailable("account_time_zone_unavailable")
    selected = body.google
    values = dict(
        account_timezone=row.time_zone,
        login_customer_id=native.login_customer_id,
        reservation_micros=definition.budget_micros,
        bidding="MANUAL_CPC",
        max_cpc_micros=selected.max_cpc_micros,
        custom_conversion_goal=option.custom_conversion_goal,
        conversion_actions=option.conversion_actions,
        country_targets=option.country_targets,
        language_targets=option.language_targets,
        google_search=True,
        search_partners=selected.search_partners,
        content_network=False,
        positive_geo_target="PRESENCE",
        negative_geo_target="PRESENCE",
        political_advertising="DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING",
        tracking_url_template="",
        final_url_suffix="",
        activation_policy="separate_exact_approval",
        omission_policy="no_optional_assets_or_automation_requested",
    )
    if isinstance(selected, GoogleTotalConfigurationIntent):
        return GoogleSearchTotalPublicationFields.model_validate(
            {
                **values,
                "total_budget_micros": selected.total_budget_micros,
                "budget_semantics": "native_total_budget_not_portfolio_proof",
            }
        )
    return GoogleSearchPublicationFields.model_validate(
        {
            **values,
            "daily_budget_micros": selected.daily_budget_micros,
            "budget_semantics": "average_daily_not_hard_cap",
        }
    )


def review(db: Session, wid: int, identifier: str) -> ProviderExecutionReview:
    row = db.scalar(
        select(ProviderExecutionReview).where(
            ProviderExecutionReview.workspace_id == wid, ProviderExecutionReview.id == identifier
        )
    )
    if row is None:
        raise HTTPException(404, "execution review unavailable")
    return row


def run(db: Session, wid: int, identifier: str) -> ProviderExecutionRun:
    row = db.scalar(
        select(ProviderExecutionRun).where(
            ProviderExecutionRun.workspace_id == wid, ProviderExecutionRun.id == identifier
        )
    )
    if row is None:
        raise HTTPException(404, "execution run unavailable")
    return row


def run_view(db: Session, row: ProviderExecutionRun) -> dict[str, Any]:
    from app.publication.customer_optimization import purpose

    review_row = review(db, row.workspace_id, row.review_id)
    purpose(review_row)
    document = review_row.document
    mandate = (
        document["plan"]["intent"]["mandate"]
        if document["purpose"] == "existing_campaign_optimize"
        else document["mandate"]
    )
    steps = list(
        db.scalars(
            select(ProviderExecutionStep)
            .where(
                ProviderExecutionStep.workspace_id == row.workspace_id,
                ProviderExecutionStep.run_id == row.id,
            )
            .order_by(ProviderExecutionStep.ordinal)
        )
    )
    attempts = {
        item.step_id: item.id
        for item in db.scalars(
            select(ProviderExecutionAttempt).where(
                ProviderExecutionAttempt.workspace_id == row.workspace_id,
                ProviderExecutionAttempt.run_id == row.id,
            )
        )
    }
    reservation = (
        db.get(ProviderExposureReservation, row.reservation_id) if row.reservation_id else None
    )
    if reservation is not None and reservation.workspace_id != row.workspace_id:
        raise unavailable("reservation_scope_unavailable")
    return {
        "id": row.id,
        "review_id": row.review_id,
        "mandate_id": mandate["mandate_id"],
        "mandate_revision": mandate["revision"],
        "purpose": document["purpose"],
        "environment": mandate["environment"],
        "state": row.state,
        "canceled": row.canceled_at is not None,
        "parent_run_id": row.parent_run_id,
        "steps": [
            {"name": s.step_id, "state": s.state, "attempt_id": attempts.get(s.step_id)}
            for s in steps
        ],
        "reservation_retained": reservation is not None and reservation.state == "held",
        "reservation_state": reservation.state if reservation else None,
        "reservation_reference": reservation.id
        if reservation is not None and document["purpose"] == "existing_campaign_optimize"
        else None,
        "effective_time": "unavailable",
        "external_cancellation_confirmed": False,
    }


def catalog_request(
    db: Session,
    wid: int,
    draft_id: str,
    actor: str,
    media: MediaStore,
    runtime: CustomerExecutionRuntime,
) -> "GoogleCatalogRequest":
    row, artifact = source_reviews.preview(db, wid, draft_id, media, runtime.clock())
    if row.approved_by is None or artifact.definition.account.platform != "google_ads":
        raise unavailable("approved_google_source_required")
    scope = account(db, wid, artifact.definition.account.account_id)
    return GoogleCatalogRequest(
        account=scope,
        draft_id=draft_id,
        draft_revision=row.revision,
        source_digest=artifact.fingerprint(),
        countries=artifact.definition.content.audience.countries,
        languages=artifact.definition.content.audience.languages,
    )


def discover(
    db: Session,
    wid: int,
    draft_id: str,
    actor: str,
    media: MediaStore,
    runtime: CustomerExecutionRuntime,
) -> "GoogleCatalog":
    if runtime.catalog is None:
        raise unavailable("named_configuration_catalog_unavailable")
    runtime.creation.authorize(db, wid, actor)
    request = catalog_request(db, wid, draft_id, actor, media, runtime)
    db.commit()
    try:
        result = runtime.catalog(request, runtime.clock())
    except GoogleCatalogUnavailable:
        raise unavailable("configuration_catalog_unavailable") from None
    runtime.creation.authorize(db, wid, actor)
    current = catalog_request(db, wid, draft_id, actor, media, runtime)
    if (
        current != request
        or result.request != request
        or not result.observed_at <= runtime.clock() < result.expires_at
    ):
        raise unavailable("configuration_catalog_changed")
    return GoogleCatalog.model_validate(result.model_dump())


def review_view(row: ProviderExecutionReview, db: Session | None = None) -> dict[str, Any]:
    from app.publication.activation_review import ActivationExecutionReview
    from app.publication.coordinator_contracts import CreationExecutionReview
    from app.publication.customer_optimization import purpose
    from app.publication.customer_optimization import review_view as optimization_view

    kind = purpose(row)
    if kind == "existing_campaign_optimize":
        if db is None:
            raise unavailable("reviewed_policy_unavailable")
        return optimization_view(row, db)
    document = (
        ActivationExecutionReview.model_validate(row.document)
        if row.document.get("purpose") == "activate"
        else CreationExecutionReview.model_validate(row.document)
    )
    plan = (
        document.creation_plan if isinstance(document, ActivationExecutionReview) else document.plan
    )
    if row.digest != document.digest() or row.plan_digest != document.plan.digest():
        raise unavailable("execution_review_integrity_unavailable")
    source = plan.review.source.definition
    return {
        "id": row.id,
        "review_digest": row.digest,
        "plan_digest": row.plan_digest,
        "purpose": document.purpose,
        "environment": document.mandate.environment,
        "campaign_name": source.content.name,
        "creative": source.content.model_dump(mode="json"),
        "platform": source.account.platform,
        "currency": source.currency,
        "reserved_upper_micros": plan.review.configuration.reservation_micros,
        "starts_at": source.starts_at.isoformat(),
        "ends_at": source.ends_at.isoformat(),
        "qualification_expires_at": document.qualification.expires_at.isoformat(),
        "configuration": plan.review.configuration.model_dump(mode="json"),
        "separate_activation_required": document.purpose == "create_paused",
        "source_revision": plan.review.source.revision,
    }
