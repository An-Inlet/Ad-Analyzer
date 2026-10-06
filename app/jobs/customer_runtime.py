"""Opt-in customer workers. No legacy collector or advertising mutation is invoked."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount, JobRun
from app.analysis.cadence import run_post_sync_analysis
from app.analysis.enums import AnalysisRunStatus
from app.analysis.policy import AnalysisCadencePolicy
from app.automation import AutomationControlKey, AutomationControlService, master_control_enabled
from app.billing.contracts import BillingTransport, get_billing_transport
from app.billing.dispatcher import run as run_billing
from app.billing.entitlements import paid_work, policy
from app.google_connections.contracts import GoogleReadTransport, get_transport
from app.google_connections.dispatcher import deliver_analysis, run_imports
from app.google_connections.models import GoogleCustomerConnection, GoogleImportCompletion
from app.mandates.service import workspace_lock
from app.settings import Settings, settings
from app.sources.contracts import SourceTransport, get_source_transport
from app.sources.dispatcher import run_tiktok
from app.workspaces.models import Workspace, WorkspaceConfiguration, WorkspaceIntegration

logger = logging.getLogger(__name__)


def _analyze(engine: Engine, job_id: int) -> object:
    # Revalidate lifecycle, paid access and account ownership at delivery time.
    # Raising keeps the durable outbox pending when a workspace temporarily disables analysis.
    with Session(engine) as db:
        job = db.get(JobRun, job_id)
        if job is None or job.account_id is None or job.connection_id is None:
            raise ValueError("analysis source unavailable")
        workspace_lock(db, job.workspace_id)
        workspace = db.get(Workspace, job.workspace_id)
        connection = db.scalar(
            select(GoogleCustomerConnection)
            .where(
                GoogleCustomerConnection.workspace_id == job.workspace_id,
                GoogleCustomerConnection.integration_id == job.connection_id,
                GoogleCustomerConnection.account_id == job.account_id,
                GoogleCustomerConnection.status == "connected",
            )
            .with_for_update()
        )
        if workspace is None or workspace.status != "active" or connection is None:
            raise ValueError("analysis source unavailable")
        completion = db.get(GoogleImportCompletion, job_id)
        if completion is None or completion.state != "pending":
            raise ValueError("analysis source retired")
        # Avoid FOR UPDATE on the account: the separate analysis session inserts FK
        # references to it. Workspace/connection locks serialize source lifecycle changes.
        account = db.scalar(
            select(AdvertisingAccount.id)
            .join(WorkspaceIntegration, WorkspaceIntegration.id == AdvertisingAccount.connection_id)
            .where(
                AdvertisingAccount.id == job.account_id,
                AdvertisingAccount.workspace_id == job.workspace_id,
                AdvertisingAccount.platform == job.platform,
                WorkspaceIntegration.id == job.connection_id,
                WorkspaceIntegration.workspace_id == job.workspace_id,
                WorkspaceIntegration.provider == job.platform.value,
                WorkspaceIntegration.status == "active",
            )
        )
        if account is None:
            raise ValueError("analysis ownership unavailable")
        if not AutomationControlService(db).effective_enabled(
            job.workspace_id, AutomationControlKey.POST_SYNC_ANALYSIS
        ):
            raise ValueError("analysis disabled")
        configuration = db.get(WorkspaceConfiguration, job.workspace_id)
        cadence = AnalysisCadencePolicy.from_workspace_analysis(
            configuration.analysis if configuration is not None else None
        )
        if not cadence.post_sync.enabled:
            raise ValueError("analysis disabled")
        paid_work(db, job.workspace_id, datetime.now(UTC))
        result = run_post_sync_analysis(engine, job_id)
        if result is None or result.status != AnalysisRunStatus.SUCCEEDED:
            raise ValueError("analysis incomplete")
        return result


def run_customer_tick(
    engine: Engine,
    *,
    configuration: Settings = settings,
    now: datetime | None = None,
    google_factory: Callable[[], GoogleReadTransport] = get_transport,
    tiktok_factory: Callable[[], SourceTransport] = lambda: get_source_transport("tiktok_ads"),
    billing_factory: Callable[[], BillingTransport] = get_billing_transport,
) -> dict[str, str]:
    """Run bounded independent stages; disabled stages never construct transports.

    Billing reconciliation is read-only maintenance independent of the ad sync kill switch.
    Analysis retains its separate workspace control, as the existing sync policy requires.
    Provider dispatchers own tenant transactions, generation checks and retry backoff.
    """
    current = now or datetime.now(UTC)
    outcomes: dict[str, str] = {}

    def stage(name: str, operation: Callable[[], object]) -> None:
        try:
            operation()
            outcomes[name] = "completed"
        except Exception:
            outcomes[name] = "failed"
            logger.warning("customer_runtime_stage_failed stage=%s", name)

    if configuration.customer_billing_scheduler_enabled:
        stage(
            "billing",
            lambda: run_billing(lambda: Session(engine), policy(), billing_factory(), current),
        )
    if (
        configuration.customer_google_scheduler_enabled
        or configuration.customer_tiktok_scheduler_enabled
    ):
        try:
            syncs_enabled = master_control_enabled(engine, AutomationControlKey.ALL_DATA_SYNCS)
        except Exception:
            syncs_enabled = False
            outcomes["sync_controls"] = "failed"
        if syncs_enabled:
            if configuration.customer_google_scheduler_enabled:
                stage("google", lambda: run_imports(engine, google_factory(), current))
            if configuration.customer_tiktok_scheduler_enabled:
                stage("tiktok", lambda: run_tiktok(engine, tiktok_factory(), current))
    if configuration.customer_analysis_outbox_enabled:
        stage("analysis_outbox", lambda: deliver_analysis(engine, _analyze, now=current))
    return outcomes
