"""Bounded local evidence only. No payloads, identifiers, providers or remediation."""

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import AwareDatetime, Field
from sqlalchemy import Select, and_, case, exists, func, or_, select
from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform, JobRunStatus
from app.ads.models import AdvertisingAccount, JobRun
from app.analysis.enums import AnalysisRunStatus
from app.analysis.models import AnalysisRun
from app.billing.models import BillingEvent, WorkspaceBilling
from app.billing.repository import customer_join
from app.goals.schemas import StrictModel
from app.google_connections.models import GoogleCustomerConnection, GoogleImportCompletion
from app.mandates.models import MandateAction
from app.meta.models import MetaConnection
from app.operations.models import OperationalObservationRecord
from app.operations.observation_contracts import Component, Outcome, Slot
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionRun,
    ProviderExecutionStep,
    ProviderExposureReservation,
    ProviderPeriodLedger,
)
from app.publication.models import PublicationStepRecord
from app.shopify.models import ShopifyConnection
from app.sources.models import SourceConnection
from app.workspaces.models import Workspace, WorkspaceIntegration

ROW_LIMIT = 500
OVERDUE_SECONDS = 900
STATEMENT_TIMEOUT_MS = 2000


class Signal(StrictModel):
    code: Literal[
        "job_failed",
        "analysis_failed",
        "analysis_running_overdue",
        "analysis_obligation_unstarted_overdue",
        "job_running_overdue",
        "billing_event_overdue",
        "billing_snapshot_overdue",
        "connection_reconnect_required",
        "connection_provider_error",
        "connection_retry_overdue",
        "renewal_outcome_unknown",
        "publication_outcome_unknown",
        "action_outcome_unknown",
        "action_dispatch_overdue",
        "provider_creation_unknown",
        "provider_creation_no_effect",
        "provider_dispatch_overdue",
        "provider_exposure_period_ended",
    ]
    environment: Literal["contract_test", "live"] | None = None
    severity: Literal["warning", "critical"]
    observed_count: int = Field(strict=True, ge=1, le=ROW_LIMIT * 4)
    oldest_observed_at: AwareDatetime | None
    action: Literal[
        "inspect_local_job",
        "inspect_billing_reconciliation",
        "review_connection",
        "preserve_reservation_reconcile_no_retry",
    ]


class HeldExposure(StrictModel):
    environment: Literal["contract_test", "live"]
    observed_held_count: int = Field(strict=True, ge=0, le=ROW_LIMIT)
    oldest_period_end: AwareDatetime | None


class RuntimeObservation(StrictModel):
    component: Component
    slot: Slot
    outcome: Outcome
    observed_at: AwareDatetime
    expected_next_at: AwareDatetime | None
    occurrence_count: int = Field(strict=True, ge=1, le=2147483647)


class Attention(StrictModel):
    schema_version: Literal["inlet.operations.attention.v1"] = "inlet.operations.attention.v1"
    observed_at: AwareDatetime
    status: Literal["attention_observed", "no_attention_observed"]
    overdue_after_seconds: int = OVERDUE_SECONDS
    row_limit_per_source: int = ROW_LIMIT
    evidence_truncated: bool
    counts_are_lower_bounds: bool
    observation_gaps: list[str] = Field(
        default_factory=lambda: [
            "storage_observations_incomplete",
            "scheduler_observations_do_not_prove_worker_liveness",
            "work_without_persisted_analysis_obligation_not_observed",
            "analysis_obligation_historical_generation_not_recorded",
            "publication_step_age_not_recorded",
            "external_alert_delivery_not_configured",
        ]
    )
    runtime_observation_status: Literal["unobserved", "observed"] = "unobserved"
    runtime_observations: list[RuntimeObservation] = Field(default_factory=list, max_length=9)
    provider_held_exposure: list[HeldExposure] = Field(default_factory=list, max_length=2)
    signals: list[Signal] = Field(max_length=22)


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def attention(db: Session, now: datetime) -> Attention:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("aware observation time required")
    now = now.astimezone(UTC)
    cutoff = now - timedelta(seconds=OVERDUE_SECONDS)
    truncated = False
    # Production uses PostgreSQL. Bound each statement as well as Python materialization.
    # Transaction-local setting disappears when the request session rolls back/closes.
    if db.get_bind().dialect.name == "postgresql":
        db.execute(select(func.set_config("statement_timeout", str(STATEMENT_TIMEOUT_MS), True)))
    evidence: dict[tuple[str, str | None], list[datetime | None]] = {}

    def rows(query: Select[Any]) -> list[Any]:
        nonlocal truncated
        values = list(db.execute(query.limit(ROW_LIMIT + 1)))
        truncated |= len(values) > ROW_LIMIT
        return values[:ROW_LIMIT]

    def add(code: str, when: datetime | None, environment: str | None = None) -> None:
        evidence.setdefault((code, environment), []).append(utc(when) if when else None)

    # Latest within each exact local job identity. A success suppresses its earlier failure.
    # The recent sample is bounded and any omitted history is explicitly marked incomplete.
    jobs = rows(
        select(
            JobRun.workspace_id,
            JobRun.connection_id,
            JobRun.account_id,
            JobRun.platform,
            JobRun.job_name,
            JobRun.status,
            JobRun.started_at,
        )
        .join(Workspace, Workspace.id == JobRun.workspace_id)
        .where(Workspace.status == "active")
        .order_by(JobRun.started_at.desc(), JobRun.id.desc())
    )
    seen = set()
    for wid, connection, account, platform, name, state, started in jobs:
        identity = wid, connection, account, platform, name
        if identity in seen:
            continue
        seen.add(identity)
        if state == JobRunStatus.FAILED:
            add("job_failed", started)
        elif state == JobRunStatus.RUNNING and utc(started) <= cutoff:
            add("job_running_overdue", started)

    # Terminal recovery is local to workspace/cadence/account. An independent
    # running row remains an observation even if a later run succeeded: this
    # report cannot establish physical termination of the earlier worker.
    analyses = rows(
        select(
            AnalysisRun.workspace_id,
            AnalysisRun.cadence,
            AnalysisRun.account_id,
            AnalysisRun.status,
            AnalysisRun.started_at,
        )
        .join(Workspace, Workspace.id == AnalysisRun.workspace_id)
        .where(Workspace.status == "active")
        .order_by(AnalysisRun.started_at.desc(), AnalysisRun.id.desc())
    )
    terminal_seen = set()
    for wid, cadence, account, state, started in analyses:
        analysis_identity = wid, cadence, account
        if state == AnalysisRunStatus.RUNNING:
            if utc(started) <= cutoff:
                add("analysis_running_overdue", started)
        elif analysis_identity not in terminal_seen:
            terminal_seen.add(analysis_identity)
            if state == AnalysisRunStatus.FAILED:
                add("analysis_failed", started)

    # A current connection is not proof of a historical job's generation. Reauth/
    # revocation retire pending outboxes; the generation-storage gap stays explicit.
    google_current = exists().where(
        GoogleCustomerConnection.workspace_id == JobRun.workspace_id,
        GoogleCustomerConnection.integration_id == JobRun.connection_id,
        GoogleCustomerConnection.account_id == JobRun.account_id,
        GoogleCustomerConnection.external_account_id == AdvertisingAccount.external_account_id,
        GoogleCustomerConnection.status == "connected",
        GoogleCustomerConnection.generation > 0,
    )
    tiktok_current = exists().where(
        SourceConnection.workspace_id == JobRun.workspace_id,
        SourceConnection.integration_id == JobRun.connection_id,
        SourceConnection.account_id == JobRun.account_id,
        SourceConnection.external_id == AdvertisingAccount.external_account_id,
        SourceConnection.provider == "tiktok_ads",
        SourceConnection.status == "connected",
        SourceConnection.generation > 0,
    )
    due = case(
        (
            GoogleImportCompletion.next_attempt_at > JobRun.finished_at,
            GoogleImportCompletion.next_attempt_at,
        ),
        else_=JobRun.finished_at,
    )
    unstarted = rows(
        select(due)
        .select_from(GoogleImportCompletion)
        .join(JobRun, JobRun.id == GoogleImportCompletion.job_id)
        .join(Workspace, Workspace.id == JobRun.workspace_id)
        .join(
            AdvertisingAccount,
            and_(
                AdvertisingAccount.id == JobRun.account_id,
                AdvertisingAccount.workspace_id == JobRun.workspace_id,
                AdvertisingAccount.connection_id == JobRun.connection_id,
                AdvertisingAccount.platform == JobRun.platform,
            ),
        )
        .join(
            WorkspaceIntegration,
            and_(
                WorkspaceIntegration.id == JobRun.connection_id,
                WorkspaceIntegration.workspace_id == JobRun.workspace_id,
            ),
        )
        .where(
            Workspace.status == "active",
            WorkspaceIntegration.status == "active",
            GoogleImportCompletion.state == "pending",
            JobRun.status == JobRunStatus.SUCCEEDED,
            JobRun.finished_at.is_not(None),
            due <= cutoff,
            or_(
                and_(
                    JobRun.platform == AdvertisingPlatform.GOOGLE_ADS,
                    WorkspaceIntegration.provider == "google_ads",
                    google_current,
                ),
                and_(
                    JobRun.platform == AdvertisingPlatform.TIKTOK_ADS,
                    WorkspaceIntegration.provider == "tiktok_ads",
                    tiktok_current,
                ),
            ),
            ~exists().where(
                AnalysisRun.workspace_id == JobRun.workspace_id,
                AnalysisRun.source_job_run_id == JobRun.id,
            ),
        )
        .order_by(due, JobRun.id)
    )
    for (observed_due,) in unstarted:
        add("analysis_obligation_unstarted_overdue", observed_due)

    events = rows(
        select(BillingEvent.received_at, BillingEvent.next_attempt_at)
        .join(WorkspaceBilling, customer_join())
        .join(Workspace, Workspace.id == WorkspaceBilling.workspace_id)
        .where(Workspace.status == "active", BillingEvent.state == "pending")
        .order_by(BillingEvent.received_at, BillingEvent.id)
    )
    for received, due in events:
        if utc(due or received) <= cutoff:
            add("billing_event_overdue", due or received)
    snapshots = rows(
        select(WorkspaceBilling.verified_at, WorkspaceBilling.next_attempt_at)
        .join(Workspace)
        .where(Workspace.status == "active", WorkspaceBilling.subscription_id.is_not(None))
        .order_by(WorkspaceBilling.verified_at.asc().nulls_first(), WorkspaceBilling.workspace_id)
    )
    for verified, due in snapshots:
        if due is not None and utc(due) > cutoff:
            continue
        if verified is None or utc(verified) <= cutoff:
            add("billing_snapshot_overdue", due or verified)

    for model in (GoogleCustomerConnection, SourceConnection, MetaConnection, ShopifyConnection):
        connections = rows(
            select(model.status, model.next_attempt_at, model.error_code)
            .join(Workspace, Workspace.id == model.workspace_id)
            .where(Workspace.status == "active", model.status != "disconnected")
            .order_by(model.id)
        )
        for state, due, error in connections:
            if error == "renewal_uncertain":
                add("renewal_outcome_unknown", None)
            elif state == "reconnect_required":
                add("connection_reconnect_required", None)
            elif state == "provider_error":
                add("connection_provider_error", None)
            elif due is not None and utc(due) <= cutoff and error is not None:
                add("connection_retry_overdue", due)

    # Unknown outcomes retain attention even for closing workspaces. No monetary totals
    # are inferred, reservations released, or publication success/absence assumed.
    steps = rows(
        select(PublicationStepRecord.state)
        .where(PublicationStepRecord.state.in_(["unknown", "conflict"]))
        .order_by(PublicationStepRecord.plan_id, PublicationStepRecord.step_id)
    )
    for _ in steps:
        add("publication_outcome_unknown", None)
    actions = rows(
        select(MandateAction.state, MandateAction.dispatch_at)
        .where(MandateAction.state.in_(["outcome_unknown", "dispatching"]))
        .order_by(MandateAction.dispatch_at.asc().nulls_first(), MandateAction.id)
    )
    for state, dispatched in actions:
        if state == "outcome_unknown":
            add("action_outcome_unknown", dispatched)
        elif dispatched is None or utc(dispatched) <= cutoff:
            add("action_dispatch_overdue", dispatched)

    # Production coordinator evidence is distinct from the legacy simulation tables.
    # Current scalar step state reflects the latest immutable receipt for its one
    # original attempt. Never filter by run/workspace activity: late uncertainty after
    # cancellation/closure still requires attention. No request or receipt JSON is read.
    held: dict[str, list[datetime]] = {"contract_test": [], "live": []}
    reservations = rows(
        select(ProviderExposureReservation.environment, ProviderPeriodLedger.ends_at)
        .join(
            ProviderPeriodLedger,
            and_(
                ProviderPeriodLedger.id == ProviderExposureReservation.ledger_id,
                ProviderPeriodLedger.workspace_id == ProviderExposureReservation.workspace_id,
                ProviderPeriodLedger.environment == ProviderExposureReservation.environment,
            ),
        )
        .where(ProviderExposureReservation.state == "held")
        .order_by(ProviderPeriodLedger.ends_at, ProviderExposureReservation.id)
    )
    for environment, end in reservations:
        held[environment].append(utc(end))
        if utc(end) <= now:
            add("provider_exposure_period_ended", end, environment)
    production_steps = rows(
        select(
            ProviderExecutionStep.state,
            ProviderExecutionAttempt.dispatched_at,
            ProviderExposureReservation.environment,
        )
        .join(
            ProviderExecutionRun,
            and_(
                ProviderExecutionRun.id == ProviderExecutionStep.run_id,
                ProviderExecutionRun.workspace_id == ProviderExecutionStep.workspace_id,
            ),
        )
        .join(
            ProviderExposureReservation,
            and_(
                ProviderExposureReservation.id == ProviderExecutionRun.reservation_id,
                ProviderExposureReservation.workspace_id == ProviderExecutionRun.workspace_id,
            ),
        )
        .outerjoin(
            ProviderExecutionAttempt,
            and_(
                ProviderExecutionAttempt.run_id == ProviderExecutionStep.run_id,
                ProviderExecutionAttempt.step_id == ProviderExecutionStep.step_id,
                ProviderExecutionAttempt.workspace_id == ProviderExecutionStep.workspace_id,
            ),
        )
        .where(
            ProviderExecutionStep.state.in_(
                ["unknown", "conflict", "verified_no_effect", "dispatching", "emitting"]
            )
        )
        .order_by(
            ProviderExecutionAttempt.dispatched_at.asc().nulls_first(),
            ProviderExecutionStep.run_id,
            ProviderExecutionStep.step_id,
        )
    )
    for state, dispatched, environment in production_steps:
        if state in {"unknown", "conflict"}:
            add("provider_creation_unknown", dispatched, environment)
        elif state == "verified_no_effect":
            add("provider_creation_no_effect", dispatched, environment)
        elif dispatched is None or utc(dispatched) <= cutoff:
            add("provider_dispatch_overdue", dispatched, environment)

    signals = []
    for (code, environment), times in sorted(evidence.items()):
        timestamps = [value for value in times if value is not None]
        uncertain = code in {
            "renewal_outcome_unknown",
            "publication_outcome_unknown",
            "action_outcome_unknown",
            "action_dispatch_overdue",
            "provider_creation_unknown",
            "provider_dispatch_overdue",
        }
        action = (
            "preserve_reservation_reconcile_no_retry"
            if uncertain or code.startswith("provider_")
            else "inspect_local_job"
            if code.startswith(("job_", "analysis_"))
            else "inspect_billing_reconciliation"
            if code.startswith("billing_")
            else "review_connection"
        )
        signals.append(
            Signal.model_validate(
                {
                    "code": code,
                    "environment": environment,
                    "severity": "critical" if uncertain else "warning",
                    "observed_count": len(times),
                    "oldest_observed_at": min(timestamps) if timestamps else None,
                    "action": action,
                }
            )
        )
    observations = list(
        db.scalars(
            select(OperationalObservationRecord)
            .order_by(OperationalObservationRecord.component, OperationalObservationRecord.slot)
            .limit(10)
        )
    )
    truncated |= len(observations) > 9
    runtime_observations = [
        RuntimeObservation.model_validate(
            {
                "component": row.component,
                "slot": row.slot,
                "outcome": row.outcome,
                "observed_at": utc(row.observed_at),
                "expected_next_at": utc(row.expected_next_at) if row.expected_next_at else None,
                "occurrence_count": row.occurrence_count,
            }
        )
        for row in observations[:9]
    ]
    return Attention(
        runtime_observation_status="observed" if observations else "unobserved",
        runtime_observations=runtime_observations,
        observed_at=now,
        status="attention_observed" if signals else "no_attention_observed",
        evidence_truncated=truncated,
        counts_are_lower_bounds=truncated,
        provider_held_exposure=[
            HeldExposure(
                environment=environment,
                observed_held_count=len(ends),
                oldest_period_end=min(ends) if ends else None,
            )
            for environment, ends in held.items()
        ],
        signals=signals,
    )
