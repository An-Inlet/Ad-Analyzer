"""Bounded local evidence only. No payloads, identifiers, providers or remediation."""

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import AwareDatetime, Field
from sqlalchemy import Select, and_, func, select
from sqlalchemy.orm import Session

from app.ads.enums import JobRunStatus
from app.ads.models import JobRun
from app.billing.models import BillingEvent, WorkspaceBilling
from app.goals.schemas import StrictModel
from app.google_connections.models import GoogleCustomerConnection
from app.mandates.models import MandateAction
from app.meta.models import MetaConnection
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
from app.workspaces.models import Workspace

ROW_LIMIT = 500
OVERDUE_SECONDS = 900
STATEMENT_TIMEOUT_MS = 2000


class Signal(StrictModel):
    code: Literal[
        "job_failed",
        "job_running_overdue",
        "billing_event_overdue",
        "billing_snapshot_overdue",
        "connection_reconnect_required",
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
            "storage_failures_not_recorded",
            "scheduler_heartbeat_not_recorded",
            "never_started_work_not_observed",
            "local_analysis_runs_not_observed",
            "publication_step_age_not_recorded",
            "external_alert_delivery_not_configured",
        ]
    )
    provider_held_exposure: list[HeldExposure] = Field(default_factory=list, max_length=2)
    signals: list[Signal] = Field(max_length=18)


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

    events = rows(
        select(BillingEvent.received_at, BillingEvent.next_attempt_at)
        .join(WorkspaceBilling, WorkspaceBilling.customer_id == BillingEvent.customer_id)
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
            if code.startswith("job_")
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
    return Attention(
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
