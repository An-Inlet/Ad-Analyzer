import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Engine, delete, exists, func, insert, or_, select
from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform, JobRunStatus
from app.ads.models import AdSet, AdvertisingAccount, Campaign, DailyMetric, JobRun
from app.ads.repository import AdvertisingMetricsRepository
from app.ads.schemas import CampaignCreate
from app.automation import AutomationControlKey, AutomationControlService
from app.imports.native import bind_meta
from app.imports.scope import ImportScopeError
from app.meta import presence_staging, staging
from app.meta.client import MetaClient, unpack_page
from app.meta.locking import lock_workspace
from app.meta.models import (
    MetaAudit,
    MetaConnection,
    MetaDetailCheckpoint,
    MetaOAuthState,
    MetaPendingGrant,
    MetaStagedMetric,
)
from app.meta.normalize import metric_values
from app.meta.security import MetaError, configuration_ready, identifier, utc
from app.meta.service import ConnectionService
from app.reported_feedback.contracts import FixedWindowLeaseV1
from app.reported_feedback.runtime import ReportedFeedbackRuntime
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
        self,
        session: Session,
        configuration: Settings,
        client: MetaClient | None = None,
        *,
        reported_feedback: ReportedFeedbackRuntime | None = None,
    ) -> None:
        self.session, self.settings = session, configuration
        self.client = client or MetaClient(configuration)
        if reported_feedback is None:
            from app.planning_reporting.runtime import configured_bundle

            engine = session.get_bind()
            bundle = configured_bundle(lambda: Session(engine), configuration)
            reported_feedback = bundle.reported if bundle else None
        self.reported_feedback = reported_feedback
        self._fixed_lease: FixedWindowLeaseV1 | None = None
        self._feedback_job_id: str | None = None

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
            if row.phase.removeprefix("rf_") == "campaigns":
                self._campaign(row, item)
            elif row.phase.removeprefix("rf_") == "adsets":
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
                presence_staging.stage_presence(self.session, row, account, staged, item)
        self.session.flush()
        if (
            row.phase.removeprefix("rf_") == "insights"
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
        account = self.session.get(AdvertisingAccount, row.account_id)
        if account is None:
            raise MetaError("meta_account_mismatch")
        prepared = presence_staging.capture_presence(self.session, row, account)
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
        from app.campaign_performance.service import publish_meta

        if self._fixed_lease is not None:
            from app.initial_planning.clock import effective_now
            from app.reported_feedback.acquisition import capture_terminal_window

            if self.reported_feedback is None:
                raise MetaError("meta_reported_feedback_unavailable")
            now = max(now, effective_now(self.session, self.reported_feedback.initial))
            completion = publish_meta(self.session, row, row.window_start, row.window_end, now)
            presence_staging.publish_presence(self.session, prepared, completion)
            capture_terminal_window(
                self.session, row, completion, self._fixed_lease, now, self.reported_feedback
            )
            row.covered_from = self._fixed_lease.rolling_covered_from
            row.covered_through = self._fixed_lease.rolling_covered_through
            row.last_sync_at = self._fixed_lease.rolling_last_sync_at
        else:
            completion = publish_meta(self.session, row, row.window_start, row.window_end, now)
            presence_staging.publish_presence(self.session, prepared, completion)
            row.covered_from = row.window_start
            row.covered_through = row.window_end
            row.last_sync_at = now
        presence_staging.clear_presence_context(self.session, row.id)
        row.window_start, row.window_end, row.cursor = None, None, None
        row.phase = "campaigns"
        self.session.add(
            JobRun(
                workspace_id=row.workspace_id,
                connection_id=row.workspace_integration_id,
                platform=PLATFORM,
                account_id=row.account_id,
                job_name="meta_ads_feedback_sync" if self._fixed_lease else "meta_ads_sync",
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
        now = utc(
            now
            or (
                self.reported_feedback.initial.clock()
                if self.reported_feedback
                else datetime.now(UTC)
            )
        )
        if not configuration_ready(self.settings) or not syncing_allowed(
            self.session, workspace_id
        ):
            return {"status": "disabled", "imported": 0}
        if not lock_workspace(self.session, workspace_id, skip_locked=True):
            return {"status": "not_connected_or_busy", "imported": 0}
        self._fixed_lease = None
        self._feedback_job_id = None
        if self.reported_feedback is not None:
            from app.reported_feedback.acquisition import lock_job_authority

            self._feedback_job_id = lock_job_authority(
                self.session, workspace_id, now, self.reported_feedback
            )
        row = self.session.scalar(
            select(MetaConnection)
            .where(
                MetaConnection.workspace_id == workspace_id,
            )
            .with_for_update(skip_locked=True)
        )
        if row is not None and row.status != "connected":
            staging.clear(self.session, row.id)
            self.session.commit()
        if row is None or row.status != "connected":
            return {"status": "not_connected_or_busy", "imported": 0}
        if row.next_attempt_at and utc(row.next_attempt_at) > now:
            return {"status": "retry_later", "imported": 0}
        rolling_due = bool(
            manual
            or row.last_sync_at is None
            or utc(row.last_sync_at)
            <= now - timedelta(minutes=self.settings.meta_sync_interval_minutes)
        )
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
            with self.session.begin_nested():
                bind_meta(self.session, row)
        except ImportScopeError:
            # Keep workspace/native locks while removing the rejected generation.
            # A full rollback here could erase a concurrent reconnect's new checkpoint.
            staging.clear(self.session, row.id)
            self.session.commit()
            return {"status": "meta_ownership_unavailable", "imported": 0}
        row.last_attempt_at = now
        try:
            with self.session.begin_nested():
                if row.phase.startswith("rf_"):
                    from app.reported_feedback.acquisition import (
                        abort_fixed_window,
                        active_lease,
                        require_lease,
                    )

                    self._fixed_lease = active_lease(self.session, row)
                    if self.reported_feedback is None or self._fixed_lease is None:
                        abort_fixed_window(
                            self.session,
                            row,
                            self._fixed_lease,
                            "reported_runtime_or_job_unavailable",
                        )
                        self.session.commit()
                        return {"status": "reported_feedback_unavailable", "imported": 0}
                    if self._fixed_lease.job_id != self._feedback_job_id:
                        raise MetaError("meta_reported_feedback_checkpoint_invalid")
                    # The ordinary importer retries these read-only transport failures
                    # after its persisted backoff. The fixed lease must get the same
                    # opportunity: its current-source guard must not mistake the last
                    # recoverable transport error for revoked connection authority.
                    # Keep this inside the page savepoint; failure restores the prior
                    # error before the normal failure handler records its new deadline.
                    if (
                        row.error_code in {"meta_unavailable", "meta_throttled"}
                        and row.next_attempt_at is not None
                        and utc(row.next_attempt_at) <= now
                    ):
                        row.error_code = None
                    require_lease(self.session, row, self._fixed_lease, now, self.reported_feedback)
                if row.window_end is None or row.window_start is None:
                    if self.reported_feedback is not None:
                        from app.reported_feedback.acquisition import claim_fixed_window

                        self._fixed_lease = claim_fixed_window(
                            self.session,
                            row,
                            account,
                            now,
                            self.reported_feedback,
                            rolling_due=rolling_due,
                            authorized_job_id=self._feedback_job_id,
                        )
                    if self._fixed_lease is not None:
                        row.window_start, row.window_end = (
                            self._fixed_lease.window.starts_on,
                            self._fixed_lease.window.ends_on,
                        )
                        row.phase, row.cursor = "rf_campaigns", None
                    else:
                        if not rolling_due:
                            self.session.commit()
                            return {"status": "up_to_date", "imported": 0}
                        end = now.astimezone(
                            ZoneInfo(account.time_zone or "UTC")
                        ).date() - timedelta(days=1)
                        row.window_start, row.window_end = end - timedelta(days=55), end
                        row.phase, row.cursor = "campaigns", None
                    presence_staging.begin_presence(self.session, row, account, now)
                token = ConnectionService(self.session, self.settings, self.client).access_token(
                    row, now
                )
                checkpoint = self.session.get(MetaDetailCheckpoint, row.id)
                if checkpoint is not None and not self.settings.meta_detail_enabled:
                    staging.clear(self.session, row.id)
                    checkpoint = None
                if checkpoint is not None:
                    complete = staging.advance(
                        self.session, row, account, checkpoint, self.client, token
                    )
                    imported = self._publish(row, now) if complete else 0
                    status = "complete" if complete else "syncing"
                else:
                    data = self.client.page(
                        row.external_account_id,
                        token,
                        row.phase.removeprefix("rf_"),
                        row.cursor,
                        row.window_start,
                        row.window_end,
                    )
                    items, cursor = unpack_page(data, row.cursor)
                    imported = self._page(row, account, items)
                    status = "syncing"
                    if cursor:
                        row.cursor = cursor
                    elif row.phase.removeprefix("rf_") == "campaigns":
                        row.phase, row.cursor = (
                            ("rf_adsets" if self._fixed_lease else "adsets"),
                            None,
                        )
                    elif row.phase.removeprefix("rf_") == "adsets":
                        row.phase, row.cursor = (
                            ("rf_insights" if self._fixed_lease else "insights"),
                            None,
                        )
                    elif self.settings.meta_detail_enabled:
                        staging.begin(self.session, row)
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
            if row.phase.startswith("rf_") and (
                code.startswith("meta_reported_feedback_")
                or code
                in {
                    "meta_campaign_inventory_changed",
                    "meta_invalid_cursor",
                    "meta_detail_checkpoint_stale",
                    "meta_detail_capacity_exceeded",
                    "meta_detail_invalid_snapshot",
                    "meta_reconnect_required",
                }
            ):
                from app.reported_feedback.acquisition import abort_fixed_window

                abort_fixed_window(self.session, row, self._fixed_lease, code)
            row.error_code, row.last_attempt_at = code, now
            row.next_attempt_at = now + timedelta(
                seconds=exc.retry_after if isinstance(exc, MetaError) else 60
            )
            if code == "meta_reconnect_required":
                from app.lifecycle.privacy import bump_workspace_export_revision

                bump_workspace_export_revision(self.session, workspace_id)
                row.status = "reconnect_required"
                staging.clear(self.session, row.id)
            if code in {
                "meta_campaign_inventory_changed",
                "meta_invalid_cursor",
                "meta_detail_checkpoint_stale",
                "meta_detail_capacity_exceeded",
                "meta_detail_invalid_snapshot",
            }:
                staging.clear(self.session, row.id)
                row.phase, row.cursor = "campaigns", None
                presence_staging.clear_campaign_presence(self.session, row.id)
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
    from app.planning_reporting.runtime import configured_bundle

    bundle = configured_bundle(lambda: Session(engine), settings)
    now = bundle.initial.clock() if bundle else datetime.now(UTC)
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
    rolling_or_feedback_due = or_(
        MetaConnection.last_sync_at.is_(None),
        MetaConnection.window_end.is_not(None),
        MetaConnection.last_sync_at <= now - timedelta(minutes=settings.meta_sync_interval_minutes),
    )
    if bundle is not None:
        from app.reported_feedback.models import ReportedFeedbackJob

        fixed_due = exists(
            select(ReportedFeedbackJob.id).where(
                ReportedFeedbackJob.workspace_id == MetaConnection.workspace_id,
                ReportedFeedbackJob.account_id == MetaConnection.account_id,
                ReportedFeedbackJob.document["anchor"]["integration_id"].as_integer()
                == MetaConnection.workspace_integration_id,
                ReportedFeedbackJob.source_connection_id == MetaConnection.id,
                ReportedFeedbackJob.source_generation == MetaConnection.generation,
                ReportedFeedbackJob.environment == bundle.profile.environment,
                ReportedFeedbackJob.policy_digest == bundle.profile.windows.digest(),
                ReportedFeedbackJob.policy_family == bundle.profile.windows.family,
                ReportedFeedbackJob.expires_at > now,
                or_(
                    ReportedFeedbackJob.state == "acquiring",
                    ReportedFeedbackJob.state.in_(("pending", "waiting"))
                    & (ReportedFeedbackJob.next_due_at <= now),
                ),
            )
        )
        rolling_or_feedback_due = or_(rolling_or_feedback_due, fixed_due)
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
                    rolling_or_feedback_due,
                )
                .order_by(MetaConnection.last_attempt_at.asc().nullsfirst())
                .limit(10)
            )
        )
    for workspace_id in ids:
        for _page in range(settings.meta_sync_pages):
            with Session(engine) as session:
                try:
                    result = MetaSyncService(
                        session, settings, reported_feedback=bundle.reported if bundle else None
                    ).page(workspace_id)
                except Exception:
                    session.rollback()
                    logging.getLogger(__name__).warning("meta_sync_failed")
                    break
            if result["status"] != "syncing":
                break
