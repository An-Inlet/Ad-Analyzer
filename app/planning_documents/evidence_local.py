"""Current local evidence fences. Callers own transactions and external identity checks."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount, Campaign
from app.billing.entitlements import paid_work
from app.campaign_performance import service as performance
from app.campaign_performance.contracts import CampaignPerformanceV1, CampaignPerformanceV2
from app.campaign_performance.models import CurrentPerformance, PerformanceCompletion
from app.commerce.ledger import lock_store, retention_floor
from app.commerce.reporting import MeasurementWindow, measurement
from app.customers.access import CustomerPrincipal, guard_customer_mutation
from app.goals import service as goals
from app.goals.progress import boundary
from app.goals.progress_contracts import GoalSalesProgressV1
from app.goals.schemas import GoalDefinition
from app.lifecycle.privacy import database_utc_now, workspace_export_revision
from app.meta.models import MetaConnection
from app.planning_documents.common import fingerprint
from app.planning_documents.context import AccountRef
from app.planning_documents.ports import EvidenceBundle, GenerationTicket, SourceFence
from app.publication import customer_intents
from app.publication.contracts import fingerprint as source_fingerprint
from app.shopify.security import utc


def changed() -> HTTPException:
    return HTTPException(409, "Planning evidence changed. Read current sources again.")


def local_authority(db: Session, principal: CustomerPrincipal, wid: int, actor: str) -> None:
    if principal.user.id != actor:
        raise changed()
    guard_customer_mutation(db, principal, wid, allowed_roles=frozenset({"owner"}))


def resolve_source_fences(
    db: Session, *, principal: CustomerPrincipal, accounts: tuple[AccountRef, ...], now: datetime
) -> tuple[SourceFence, ...]:
    fences = []
    for ref in sorted(accounts, key=lambda value: value.account_id):
        local_authority(db, principal, ref.workspace_id, principal.user.id)
        paid_work(db, ref.workspace_id, now)
        scope = customer_intents.account(db, ref.workspace_id, ref.account_id)
        current = AccountRef(
            workspace_id=scope.workspace_id,
            account_id=scope.account.account_id,
            connection_id=scope.account.connection_id,
            platform=scope.account.platform,
            connection_version=scope.connection_version,
        )
        if current != ref:
            raise changed()
        fences.append(
            SourceFence(
                account=current,
                source_binding_digest=source_fingerprint(
                    "inlet.planning-source.v1", scope.model_dump(mode="json")
                ),
                source_revision=scope.connection_version,
                privacy_revision=workspace_export_revision(db, ref.workspace_id),
            )
        )
    return tuple(fences)


def check_goal(db: Session, ticket: GenerationTicket) -> None:
    expected = ticket.inputs.goal
    goal = goals.owned(db, expected.workspace_id, expected.goal_id)
    db.refresh(goal)
    revision = goals.current(db, goal)
    db.refresh(revision)
    if (
        goal.revision != expected.revision
        or revision.confirmed_at is None
        or goal.confirmed_preview_id != expected.confirmation_reference
        or revision.definition is None
        or GoalDefinition.model_validate(revision.definition) != expected.definition
    ):
        raise changed()


def ordinary_meta(
    db: Session,
    wid: int,
    account_id: int,
    document: PerformanceCompletion | CampaignPerformanceV1 | CampaignPerformanceV2,
) -> None:
    """Do not enter alternate reporting acquisition/anchor provenance from planning."""
    source = db.scalar(
        select(MetaConnection)
        .where(MetaConnection.workspace_id == wid, MetaConnection.account_id == account_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        source is None
        or source.last_sync_at is None
        or (source.covered_from, source.covered_through, utc(source.last_sync_at))
        != (
            document.starts_on,
            document.ends_on,
            utc(document.completed_at),
        )
    ):
        raise changed()


def commerce_binding(document: GoalSalesProgressV1, privacy: int) -> str:
    return fingerprint(
        "commerce-source",
        {
            "workspace_id": document.workspace_id,
            "store_id": document.store_id,
            "source_revision": document.source_revision,
            "source_watermark": (
                utc(document.source_watermark).isoformat()
                if document.source_watermark is not None
                else None
            ),
            "definition_digest": document.definition_digest,
            "privacy_revision": privacy,
        },
    )


def recheck_local_sources(
    db: Session,
    *,
    principal: CustomerPrincipal,
    ticket: GenerationTicket,
    bundle: EvidenceBundle,
    now: datetime,
) -> None:
    bundle.assert_ticket(ticket)
    wid = ticket.inputs.workspace_id
    if (principal.user.id, principal.session.digest) != (ticket.actor_id, ticket.session_digest):
        raise changed()
    local_authority(db, principal, wid, ticket.actor_id)
    check_goal(db, ticket)
    fresh = resolve_source_fences(db, principal=principal, accounts=ticket.inputs.accounts, now=now)
    if {f.account.account_id: f for f in fresh} != {
        f.account.account_id: f for f in ticket.sources
    }:
        raise changed()
    if workspace_export_revision(db, wid) != ticket.privacy_revision:
        raise changed()

    def authorize(session: Session, workspace: int, actor: str) -> None:
        local_authority(session, principal, workspace, actor)

    for catalog in bundle.catalogs:
        observed = catalog.catalog.native_observation
        account = db.get(AdvertisingAccount, observed.account_id, populate_existing=True)
        if account is None or (account.currency_code, account.time_zone) != (
            observed.currency,
            observed.time_zone,
        ):
            raise changed()
    for gap in bundle.gaps:
        if gap.reporting_pin is not None:
            pin = gap.reporting_pin
            if gap.account is None:
                raise changed()
            campaign = db.scalar(
                select(Campaign)
                .where(
                    Campaign.account_id == gap.account.account_id,
                    Campaign.platform == gap.account.platform,
                    Campaign.external_campaign_id == pin.native_campaign_id,
                )
                .execution_options(populate_existing=True)
            )
            if campaign is None or campaign.id != pin.campaign_id:
                raise changed()
            completion = db.get(PerformanceCompletion, pin.completion_id, populate_existing=True)
            if completion is None:
                raise changed()
            if gap.account.platform == "meta_ads":
                ordinary_meta(db, wid, gap.account.account_id, completion)
            document = performance.read_current(
                db,
                wid,
                ticket.actor_id,
                gap.account.account_id,
                campaign.id,
                pin.completion_id,
                authorize,
            )
            actual_start = boundary(document.starts_on, ZoneInfo(document.time_zone))
            actual_end = boundary(
                document.ends_on + timedelta(days=1), ZoneInfo(document.time_zone)
            )
            if (
                fingerprint("campaign-performance", document.model_dump(mode="json"))
                != pin.document_digest
                or (pin.reporting_window.starts_at, pin.reporting_window.ends_at_exclusive)
                != (actual_start, actual_end)
                or pin.reporting_window
                in (ticket.inputs.reporting_window, ticket.inputs.comparison_window)
            ):
                raise changed()
        if (
            gap.reason == "current_reporting_unavailable"
            and gap.account is not None
            and db.get(CurrentPerformance, gap.account.account_id, populate_existing=True)
            is not None
        ):
            raise changed()
        if gap.reason == "campaign_reporting_unavailable" and gap.account is not None:
            catalog = next(c for c in bundle.catalogs if c.reference.account == gap.account)
            known = {
                p.native_campaign_id for p in bundle.performance if p.target.account == gap.account
            }
            for native_target in catalog.catalog.targets:
                if (
                    native_target.entity.kind != "campaign"
                    or native_target.entity.reference.entity_id in known
                ):
                    continue
                if (
                    db.scalar(
                        select(Campaign.id).where(
                            Campaign.account_id == gap.account.account_id,
                            Campaign.platform == gap.account.platform,
                            Campaign.external_campaign_id
                            == native_target.entity.reference.entity_id,
                        )
                    )
                    is not None
                ):
                    raise changed()
    for item in bundle.performance:
        target, old = item.target, item.document
        if item.reference.source_revision != str(old.generation):
            raise changed()
        campaign = db.scalar(
            select(Campaign)
            .where(
                Campaign.account_id == target.account.account_id,
                Campaign.platform == target.account.platform,
                Campaign.external_campaign_id == item.native_campaign_id,
            )
            .execution_options(populate_existing=True)
        )
        if campaign is None or campaign.id != old.campaign_id:
            raise changed()
        if target.account.platform == "meta_ads":
            ordinary_meta(db, wid, target.account.account_id, old)
        current = performance.read_current(
            db,
            wid,
            ticket.actor_id,
            target.account.account_id,
            campaign.id,
            old.completion_id,
            authorize,
        )
        if current != old:
            raise changed()
    if bundle.commerce is not None:
        doc = bundle.commerce.document
        store = lock_store(db, ticket.inputs.goal.definition.store_id, wid)
        check_time = max(utc(now), database_utc_now(db))
        watermark = utc(store.last_sync_at) if store.last_sync_at else None
        if (
            (doc.source_revision, doc.source_watermark, doc.import_in_progress)
            != (store.revision, watermark, store.window_end is not None)
            or (store.currency, store.time_zone) != (doc.currency, doc.time_zone)
            or bundle.commerce.reference.source_binding_digest
            != commerce_binding(doc, ticket.privacy_revision)
        ):
            raise changed()
        definition = ticket.inputs.goal.definition
        zone = ZoneInfo(definition.target_window.time_zone)
        today = check_time.astimezone(zone).date()
        window = definition.target_window
        if doc.status == "not_started":
            if today >= window.start or doc.reasons != ("no_closed_days",):
                raise changed()
        elif doc.coverage is not None:
            if watermark is None:
                raise changed()
            end = min(window.end, today, watermark.astimezone(zone).date())
            if (doc.coverage.starts_at, doc.coverage.ends_at_exclusive) != (
                boundary(window.start, zone),
                boundary(end, zone),
            ):
                raise changed()
            result = measurement(
                db,
                wid,
                store.id,
                MeasurementWindow(
                    start=window.start,
                    end=end,
                    time_basis="cumulative",
                    currency=window.currency,
                    time_zone=window.time_zone,
                ),
                now=check_time,
                snapshot=False,
            )
            reasons = list(result["reasons"])
            if not timedelta(0) <= check_time - watermark <= timedelta(hours=24):
                reasons.append("stale_source")
            if doc.coverage.starts_at < retention_floor(check_time, store.time_zone):
                reasons.append("outside_retention")
            reasons = list(dict.fromkeys(reasons))
            amount = None if reasons else result["net_sales_micros"]
            if (doc.net_sales_micros, doc.reasons) != (amount, tuple(reasons)):
                raise changed()
        elif doc.reasons == ("missing_history",):
            if watermark is not None or today < window.start:
                raise changed()
        elif doc.reasons == ("no_closed_days",):
            if (
                watermark is None
                or today < window.start
                or min(window.end, today, watermark.astimezone(zone).date()) > window.start
            ):
                raise changed()
        else:
            # An ambiguous source/ownership error is not missing-history evidence.
            raise changed()
    final = max(utc(now), database_utc_now(db))
    refs = [c.reference for c in bundle.catalogs] + [p.reference for p in bundle.performance]
    refs += [c.reference for c in bundle.context]
    if bundle.commerce is not None:
        refs.append(bundle.commerce.reference)
    if (
        any(final >= ref.expires_at for ref in refs)
        or final.timestamp() >= principal.session.expires_at
    ):
        raise changed()
    local_authority(db, principal, wid, ticket.actor_id)
    paid_work(db, wid, final)
