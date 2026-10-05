import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Engine, delete, func, insert, or_, select
from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform, JobRunStatus
from app.ads.models import AdSet, AdvertisingAccount, Campaign, DailyMetric, JobRun
from app.ads.repository import AdvertisingMetricsRepository
from app.ads.schemas import CampaignCreate
from app.automation import AutomationControlKey, AutomationControlService
from app.imports.native import bind_meta
from app.imports.scope import ImportScopeError
from app.meta.client import MetaClient, unpack_page
from app.meta.models import (
    MetaAudit,
    MetaConnection,
    MetaOAuthState,
    MetaPendingGrant,
    MetaStagedMetric,
)
from app.meta.normalize import metric_values
from app.meta.security import MetaError, configuration_ready, identifier, utc
from app.meta.service import ConnectionService
from app.settings import Settings, settings

PLATFORM = AdvertisingPlatform.META_ADS


def syncing_allowed(session: Session, workspace_id: int) -> bool:
    controls = AutomationControlService(session)
    return controls.master_enabled(
        AutomationControlKey.ALL_DATA_SYNCS
    ) and controls.effective_enabled(workspace_id, AutomationControlKey.META_ADS_SYNC)


def _label(value: object, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MetaError("meta_invalid_response")
    return value[:limit]


class MetaSyncService:
    def __init__(
        self, session: Session, configuration: Settings, client: MetaClient | None = None
    ) -> None:
        self.session, self.settings = session, configuration
        self.client = client or MetaClient(configuration)

    def _campaign(
        self, row: MetaConnection, item: dict[str, Any], *, insight: bool = False
    ) -> Campaign:
        external = identifier(item["campaign_id"] if insight else item["id"])
        name = _label(item["campaign_name"] if insight else item["name"], 255)
        repository = AdvertisingMetricsRepository(self.session)
        existing = self.session.scalar(
            select(Campaign).where(
                Campaign.account_id == row.account_id,
                Campaign.platform == PLATFORM,
                Campaign.external_campaign_id == external,
            )
        )
        # Insights can include archived campaigns absent from the inventory edge.
        if insight and existing:
            return existing
        return repository.upsert_campaign(
            CampaignCreate(
                account_id=row.account_id,
                platform=PLATFORM,
                external_campaign_id=external,
                name=name,
                status=existing.status
                if insight and existing
                else str(item.get("status", "UNKNOWN"))[:64],
                channel_type=str(item.get("objective", "UNKNOWN"))[:64],
            )
        )

    def _page(
        self, row: MetaConnection, account: AdvertisingAccount, items: list[dict[str, Any]]
    ) -> int:
        for item in items:
            if identifier(item["account_id"]) != row.external_account_id:
                raise MetaError("meta_account_mismatch")
            if row.phase == "campaigns":
                self._campaign(row, item)
            elif row.phase == "adsets":
                campaign = self.session.scalar(
                    select(Campaign).where(
                        Campaign.account_id == row.account_id,
                        Campaign.platform == PLATFORM,
                        Campaign.external_campaign_id == identifier(item["campaign_id"]),
                    )
                )
                if campaign is None:
                    raise MetaError("meta_campaign_inventory_changed")
                external = identifier(item["id"])
                adset = self.session.scalar(
                    select(AdSet).where(
                        AdSet.campaign_id == campaign.id,
                        AdSet.platform == PLATFORM,
                        AdSet.external_ad_set_id == external,
                    )
                )
                if adset is None:
                    adset = AdSet(
                        campaign_id=campaign.id, platform=PLATFORM, external_ad_set_id=external
                    )
                    self.session.add(adset)
                adset.name, adset.status = (
                    _label(item["name"], 255),
                    str(item.get("status", "UNKNOWN"))[:64],
                )
            else:
                assert row.window_start is not None and row.window_end is not None
                values = metric_values(
                    item,
                    row.external_account_id,
                    account.currency_code,
                    row.window_start,
                    row.window_end,
                    row.conversion_action_type,
                )
                campaign = self._campaign(row, item, insight=True)
                staged = self.session.get(
                    MetaStagedMetric, (row.id, campaign.id, values["metric_date"])
                )
                if staged is None:
                    staged = MetaStagedMetric(
                        connection_id=row.id, campaign_id=campaign.id, **values
                    )
                    self.session.add(staged)
                else:
                    for name, value in values.items():
                        setattr(staged, name, value)
        self.session.flush()
        if (
            row.phase == "insights"
            and (
                self.session.scalar(
                    select(func.count())
                    .select_from(MetaStagedMetric)
                    .where(MetaStagedMetric.connection_id == row.id)
                )
                or 0
            )
            > 100_000
        ):
            raise MetaError("meta_import_capacity_exceeded")
        return len(items)

    def _publish(self, row: MetaConnection, now: datetime) -> int:
        assert row.window_start is not None and row.window_end is not None
        campaign_ids = select(Campaign.id).where(
            Campaign.account_id == row.account_id, Campaign.platform == PLATFORM
        )
        self.session.execute(
            delete(DailyMetric).where(
                DailyMetric.campaign_id.in_(campaign_ids),
                DailyMetric.platform == PLATFORM,
                DailyMetric.entity_type == "campaign",
                DailyMetric.metric_date >= row.window_start,
                DailyMetric.metric_date <= row.window_end,
            )
        )
        offset, total = 0, 0
        while True:
            rows = list(
                self.session.scalars(
                    select(MetaStagedMetric)
                    .where(
                        MetaStagedMetric.connection_id == row.id,
                        MetaStagedMetric.campaign_id.in_(campaign_ids),
                    )
                    .order_by(MetaStagedMetric.campaign_id, MetaStagedMetric.metric_date)
                    .offset(offset)
                    .limit(500)
                )
            )
            if not rows:
                break
            self.session.execute(
                insert(DailyMetric),
                [
                    {
                        "platform": PLATFORM,
                        "entity_type": "campaign",
                        "entity_id": m.campaign_id,
                        "campaign_id": m.campaign_id,
                        "metric_date": m.metric_date,
                        "impressions": m.impressions,
                        "clicks": m.clicks,
                        "cost_micros": m.cost_micros,
                        "conversions": m.conversions,
                        "conversion_value_micros": m.conversion_value_micros,
                    }
                    for m in rows
                ],
            )
            offset += len(rows)
            total += len(rows)
        self.session.execute(
            delete(MetaStagedMetric).where(MetaStagedMetric.connection_id == row.id)
        )
        row.covered_from = row.window_start
        row.covered_through = row.window_end
        row.last_sync_at, row.window_start, row.window_end, row.cursor = now, None, None, None
        row.phase = "campaigns"
        self.session.add(
            JobRun(
                workspace_id=row.workspace_id,
                connection_id=row.workspace_integration_id,
                platform=PLATFORM,
                account_id=row.account_id,
                job_name="meta_ads_sync",
                status=JobRunStatus.SUCCEEDED,
                started_at=now,
                finished_at=now,
                records_processed=total,
            )
        )
        return total

    def page(
        self, workspace_id: int, *, now: datetime | None = None, manual: bool = False
    ) -> dict[str, Any]:
        now = utc(now or datetime.now(UTC))
        if not configuration_ready(self.settings) or not syncing_allowed(
            self.session, workspace_id
        ):
            return {"status": "disabled", "imported": 0}
        row = self.session.scalar(
            select(MetaConnection)
            .where(
                MetaConnection.workspace_id == workspace_id,
            )
            .with_for_update(skip_locked=True)
        )
        if row is None or row.status != "connected":
            return {"status": "not_connected_or_busy", "imported": 0}
        if row.next_attempt_at and utc(row.next_attempt_at) > now:
            return {"status": "retry_later", "imported": 0}
        if (
            not manual
            and row.window_end is None
            and row.last_sync_at
            and utc(row.last_sync_at)
            > now - timedelta(minutes=self.settings.meta_sync_interval_minutes)
        ):
            return {"status": "up_to_date", "imported": 0}
        account = self.session.scalar(
            select(AdvertisingAccount).where(
                AdvertisingAccount.id == row.account_id,
                AdvertisingAccount.workspace_id == workspace_id,
                AdvertisingAccount.platform == PLATFORM,
                AdvertisingAccount.external_account_id == row.external_account_id,
            )
        )
        if account is None:
            return {"status": "meta_account_mismatch", "imported": 0}
        try:
            bind_meta(self.session, row)
        except ImportScopeError:
            self.session.rollback()
            return {"status": "meta_ownership_unavailable", "imported": 0}
        row.last_attempt_at = now
        try:
            with self.session.begin_nested():
                if row.window_end is None or row.window_start is None:
                    end = now.astimezone(ZoneInfo(account.time_zone or "UTC")).date() - timedelta(
                        days=1
                    )
                    row.window_start, row.window_end = end - timedelta(days=55), end
                    row.phase, row.cursor = "campaigns", None
                    self.session.execute(
                        delete(MetaStagedMetric).where(MetaStagedMetric.connection_id == row.id)
                    )
                token = ConnectionService(self.session, self.settings, self.client).access_token(
                    row, now
                )
                data = self.client.page(
                    row.external_account_id,
                    token,
                    row.phase,
                    row.cursor,
                    row.window_start,
                    row.window_end,
                )
                items, cursor = unpack_page(data, row.cursor)
                imported = self._page(row, account, items)
                status = "syncing"
                if cursor:
                    row.cursor = cursor
                elif row.phase == "campaigns":
                    row.phase, row.cursor = "adsets", None
                elif row.phase == "adsets":
                    row.phase, row.cursor = "insights", None
                else:
                    imported = self._publish(row, now)
                    status = "complete"
                row.error_code, row.next_attempt_at = None, None
                self.session.add(
                    MetaAudit(
                        workspace_id=workspace_id,
                        action="sync_page",
                        actor_role="operator" if manual else "scheduler",
                        record_count=imported,
                    )
                )
            self.session.commit()
            return {"status": status, "imported": imported}
        except (MetaError, KeyError, TypeError, ValueError) as exc:
            code = exc.code if isinstance(exc, MetaError) else "meta_invalid_response"
            row.error_code, row.last_attempt_at = code, now
            row.next_attempt_at = now + timedelta(
                seconds=exc.retry_after if isinstance(exc, MetaError) else 60
            )
            if code == "meta_reconnect_required":
                row.status = "reconnect_required"
            if code in {"meta_campaign_inventory_changed", "meta_invalid_cursor"}:
                row.phase, row.cursor = "campaigns", None
                self.session.execute(
                    delete(MetaStagedMetric).where(MetaStagedMetric.connection_id == row.id)
                )
            # A failed import never replaces an earlier complete metric snapshot.
            self.session.add(
                JobRun(
                    workspace_id=workspace_id,
                    connection_id=row.workspace_integration_id,
                    account_id=row.account_id,
                    platform=PLATFORM,
                    job_name="meta_ads_sync",
                    status=JobRunStatus.FAILED,
                    started_at=now,
                    finished_at=now,
                    records_processed=0,
                    error_message=code,
                )
            )
            self.session.add(
                MetaAudit(
                    workspace_id=workspace_id,
                    action=code,
                    actor_role="operator" if manual else "scheduler",
                )
            )
            self.session.commit()
            return {"status": code, "imported": 0}


def run_meta_tick(engine: Engine) -> None:
    now = datetime.now(UTC)
    # Expiring pending credentials are cleaned even when imports are switched off.
    with Session(engine) as session:
        session.execute(
            delete(MetaPendingGrant)
            .execution_options(synchronize_session="fetch")
            .where(MetaPendingGrant.expires_at <= now)
        )
        session.execute(
            delete(MetaOAuthState)
            .execution_options(synchronize_session="fetch")
            .where(MetaOAuthState.expires_at <= now)
        )
        session.commit()
    if not configuration_ready(settings):
        return
    with Session(engine) as session:
        ids = list(
            session.scalars(
                select(MetaConnection.workspace_id)
                .where(
                    MetaConnection.status == "connected",
                    or_(
                        MetaConnection.next_attempt_at.is_(None),
                        MetaConnection.next_attempt_at <= now,
                    ),
                    or_(
                        MetaConnection.last_sync_at.is_(None),
                        MetaConnection.window_end.is_not(None),
                        MetaConnection.last_sync_at
                        <= now - timedelta(minutes=settings.meta_sync_interval_minutes),
                    ),
                )
                .order_by(MetaConnection.last_attempt_at.asc().nullsfirst())
                .limit(10)
            )
        )
    for workspace_id in ids:
        for _page in range(settings.meta_sync_pages):
            with Session(engine) as session:
                try:
                    result = MetaSyncService(session, settings).page(workspace_id)
                except Exception:
                    session.rollback()
                    logging.getLogger(__name__).warning("meta_sync_failed")
                    break
            if result["status"] != "syncing":
                break
