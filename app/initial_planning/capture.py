"""Prospective aggregate captures. Historical documents never masquerade as current reports."""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount
from app.campaign_performance.contracts import CampaignPerformanceV1
from app.campaign_performance.models import PerformanceCompletion
from app.campaign_performance.service import read_current, require_active_integration
from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.initial_planning.contracts import CohortV1, InitialPlanningConfiguration, ObservationV1
from app.initial_planning.models import ObservationRow
from app.initial_planning.runtime import InitialPlanningRuntime
from app.meta.models import MetaConnection
from app.meta.security import PURCHASE_ACTIONS, utc
from app.publication.customer_authority import bind_authority


def unavailable(code: str) -> HTTPException:
    return HTTPException(409, code)


def configuration(runtime: InitialPlanningRuntime) -> InitialPlanningConfiguration:
    policy = runtime.configuration
    if policy is None:
        raise unavailable("initial_planning_configuration_unavailable")
    if policy.supported_event not in PURCHASE_ACTIONS:
        raise unavailable("initial_planning_event_unsupported")
    return policy


def source_current(
    db: Session, wid: int, account_id: int, generation: int | None = None
) -> MetaConnection:
    source = db.scalar(
        select(MetaConnection)
        .where(
            MetaConnection.workspace_id == wid,
            MetaConnection.account_id == account_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    account = db.get(AdvertisingAccount, account_id, populate_existing=True)
    if (
        source is None
        or account is None
        or account.workspace_id != wid
        or source.status != "connected"
        or source.error_code
        or account.external_account_id != source.external_account_id
        or account.connection_id != source.workspace_integration_id
        or (generation is not None and source.generation != generation)
    ):
        raise unavailable("initial_planning_source_unavailable")
    require_active_integration(db, account)
    return source


def capture_current(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    workspace_id: int,
    account_id: int,
    campaign_id: int,
    runtime: InitialPlanningRuntime,
) -> ObservationV1:
    policy = configuration(runtime)
    authorize = bind_authority(principal, provider)
    report = read_current(
        db, workspace_id, principal.user.id, account_id, campaign_id, None, authorize
    )
    if (
        not isinstance(report, CampaignPerformanceV1)
        or report.selected_event != policy.supported_event
    ):
        raise unavailable("initial_planning_objective_unsupported")
    try:
        ZoneInfo(report.time_zone)
    except (ValueError, KeyError):
        raise unavailable("initial_observation_calendar_unavailable") from None
    now = runtime.clock()
    if not report.completed_at <= now:
        raise unavailable("initial_planning_future_report")
    existing = db.scalar(
        select(ObservationRow).where(
            ObservationRow.workspace_id == workspace_id,
            ObservationRow.account_id == account_id,
            ObservationRow.campaign_id == campaign_id,
            ObservationRow.completion_id == report.completion_id,
            ObservationRow.environment == policy.environment,
        )
    )
    if existing is not None:
        return read_observation(db, principal, provider, workspace_id, existing.id, runtime)
    total = (
        db.scalar(
            select(func.count())
            .select_from(ObservationRow)
            .where(
                ObservationRow.workspace_id == workspace_id,
                ObservationRow.account_id == account_id,
                ObservationRow.campaign_id == campaign_id,
                ObservationRow.environment == policy.environment,
            )
        )
        or 0
    )
    if total >= policy.maximum_observations:
        raise unavailable("initial_observation_capacity_reached")
    completion = db.get(PerformanceCompletion, report.completion_id)
    assert completion is not None
    cohort = CohortV1(
        workspace_id=workspace_id,
        account_id=account_id,
        campaign_id=campaign_id,
        selected_event=report.selected_event,
        currency=report.currency,
        time_zone=report.time_zone,
        query_version=completion.query_version,
    )
    document = ObservationV1(
        id=uuid4().hex,
        cohort=cohort,
        environment=policy.environment,
        completion_id=report.completion_id,
        manifest_digest=report.manifest_digest,
        generation=report.generation,
        privacy_revision=report.privacy_revision,
        starts_on=report.starts_on,
        ends_on=report.ends_on,
        completed_at=report.completed_at,
        captured_at=now,
        expires_at=now + timedelta(seconds=policy.retention_seconds),
        retention_policy_digest=policy.digest(),
        reported_day_count=report.reported_day_count,
        impressions=report.impressions,
        clicks=report.clicks,
        spend_micros=report.spend_micros,
        conversions=Decimal(report.conversions) if report.conversions is not None else None,
        conversion_value_micros=report.conversion_value_micros,
    )
    authorize(db, workspace_id, principal.user.id)
    if runtime.clock() >= document.expires_at:
        raise unavailable("initial_observation_expired")
    db.add(
        ObservationRow(
            id=document.id,
            workspace_id=workspace_id,
            account_id=account_id,
            campaign_id=campaign_id,
            document=document.model_dump(mode="json"),
            document_digest=document.digest(),
            expires_at=document.expires_at,
            environment=document.environment,
            completion_id=document.completion_id,
            generation=document.generation,
            privacy_revision=document.privacy_revision,
            cohort_digest=cohort.digest(),
            captured_at=now,
            retention_policy_digest=document.retention_policy_digest,
        )
    )
    db.flush()
    return document


def read_observation(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    workspace_id: int,
    observation_id: str,
    runtime: InitialPlanningRuntime,
) -> ObservationV1:
    policy = configuration(runtime)
    authorize = bind_authority(principal, provider)
    authorize(db, workspace_id, principal.user.id)
    row = db.scalar(
        select(ObservationRow)
        .where(
            ObservationRow.id == observation_id,
            ObservationRow.workspace_id == workspace_id,
        )
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise unavailable("initial_observation_unavailable")
    document = ObservationV1.model_validate(row.document)
    if (
        document.digest() != row.document_digest
        or document.id != row.id
        or (document.cohort.workspace_id, document.cohort.account_id, document.cohort.campaign_id)
        != (row.workspace_id, row.account_id, row.campaign_id)
        or document.completion_id != row.completion_id
        or document.generation != row.generation
        or document.environment != policy.environment
        or document.environment != row.environment
        or document.cohort.digest() != row.cohort_digest
        or document.retention_policy_digest != row.retention_policy_digest
        or document.privacy_revision != row.privacy_revision
        or document.captured_at != utc(row.captured_at)
        or document.expires_at != utc(row.expires_at)
        or not document.captured_at <= runtime.clock() < document.expires_at
    ):
        raise unavailable("initial_observation_expired_or_changed")
    source = source_current(db, workspace_id, row.account_id, document.generation)
    account = db.get(AdvertisingAccount, row.account_id, populate_existing=True)
    completion = db.get(PerformanceCompletion, row.completion_id, populate_existing=True)
    if (
        account is None
        or completion is None
        or account.currency_code != document.cohort.currency
        or account.time_zone != document.cohort.time_zone
        or completion.manifest_digest != document.manifest_digest
        or completion.source_connection_ref != str(source.id)
        or completion.generation != document.generation
        or completion.selected_event != document.cohort.selected_event
        or completion.query_version != document.cohort.query_version
        or completion.starts_on != document.starts_on
        or completion.ends_on != document.ends_on
        or utc(completion.completed_at) != document.completed_at
        or source.conversion_action_type != document.cohort.selected_event
    ):
        raise unavailable("initial_observation_basis_changed")
    # Captured privacy counter is audit-only. Actual semantic privacy hooks physically
    # erase capsules; export-only correction invalidation must not rewrite history.
    authorize(db, workspace_id, principal.user.id)
    if runtime.clock() >= document.expires_at:
        raise unavailable("initial_observation_expired")
    return document
