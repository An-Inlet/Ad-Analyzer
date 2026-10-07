"""Current owned preview and independently consented same-ledger policy comparison."""

from collections.abc import Callable
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.initial_planning.models import PreviewRow
from app.initial_planning.preview import read_preview
from app.initial_planning.preview_v2 import InitialPreviewV2, PreviewIntentV2
from app.initial_planning.review_v2_api_contracts import InitialPreviewExecutionRuntime
from app.publication import customer_intents, execution_mandates
from app.publication.execution_contracts import ProviderMandateBinding, ProviderMandatePolicy
from app.publication.execution_models import ProviderExecutionRevision


def unavailable() -> HTTPException:
    return HTTPException(409, "initial_preview_execution_retracted_or_changed")


def configured(runtime: InitialPreviewExecutionRuntime) -> bool:
    native = runtime.optimization
    attached = native.initial_planning if native is not None else None
    return bool(
        native is not None
        and native.configured is not None
        and attached is not None
        and attached.profile is not None
        and runtime.planning.profile is not None
        and attached.configuration is not None
        and runtime.planning.configuration is not None
        and attached.profile.digest() == runtime.planning.profile.digest()
        and attached.configuration.digest() == runtime.planning.configuration.digest()
        and native.execution.environment == runtime.planning.profile.environment
    )


def current_preview(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    wid: int,
    preview_id: str,
    runtime: InitialPreviewExecutionRuntime,
) -> tuple[InitialPreviewV2, PreviewRow, PreviewIntentV2]:
    value = read_preview(db, principal, provider, wid, preview_id, runtime.planning)
    row = db.get(PreviewRow, preview_id, populate_existing=True)
    if not isinstance(value, InitialPreviewV2) or row is None:
        raise unavailable()
    intent = PreviewIntentV2.model_validate(row.intent)
    if (
        value.recommendation_status != "proposed"
        or value.direction not in {"increase", "decrease"}
        or value.native_observation is None
        or value.after_budget_micros is None
        or value.native_observation.budget_mode != "daily"
        or value.native_observation.currency != "USD"
        or intent.mandate_id is None
        or intent.mandate_revision is None
        or row.mandate_digest is None
    ):
        raise unavailable()
    return value, row, intent


def policy_pair(
    db: Session,
    wid: int,
    value: InitialPreviewV2,
    row: PreviewRow,
    intent: PreviewIntentV2,
    execution: ProviderMandateBinding,
    actor: str,
    runtime: InitialPreviewExecutionRuntime,
    clock: Callable[[], datetime],
) -> tuple[ProviderMandateBinding, ProviderMandatePolicy]:
    if (
        runtime.optimization is None
        or runtime.optimization.configured is None
        or intent.mandate_id is None
        or intent.mandate_revision is None
        or value.native_observation is None
    ):
        raise unavailable()
    planning = customer_intents.binding(db, wid, intent.mandate_id, intent.mandate_revision)
    _, before = execution_mandates.checked(db, wid, planning, actor, clock)
    _, after = execution_mandates.checked(db, wid, execution, actor, clock)
    revision = db.get(
        ProviderExecutionRevision,
        (execution.mandate_id, execution.revision),
        populate_existing=True,
    )
    if revision is None or revision.origin_kind != "optimization_customer_v1":
        raise unavailable()
    runtime.optimization.configured.origin_guard(db, revision, after)
    native = value.native_observation
    if (
        planning.mandate_id == execution.mandate_id
        or planning.consent_id == execution.consent_id
        or planning.ledger_id != execution.ledger_id
        or planning.environment != execution.environment
        or execution.environment != value.environment
        or before.digest() != row.mandate_digest
        or before.goal_id != value.objective.goal_id
        or after.goal_id != before.goal_id
        or before.goal_revision != value.objective.goal_revision
        or after.goal_revision != before.goal_revision
        or after.starts_at != before.starts_at
        or after.ends_at != before.ends_at
        or after.currency != before.currency
        or after.time_zone != before.time_zone
        or after.total_cap_micros != before.total_cap_micros
        or after.per_plan_cap_micros > before.per_plan_cap_micros
        or after.positive_change_cap_micros > before.positive_change_cap_micros
        or sorted(a.digest() for a in after.accounts) != sorted(a.digest() for a in before.accounts)
        or native.request.scope.digest() not in {a.digest() for a in after.accounts}
        or after.currency != native.currency
        or after.time_zone != native.time_zone
        or after.allowed_target_set_digest != native.budget_owner.target_set_digest()
        or "existing_campaign_optimize" not in after.allowed_purposes
    ):
        raise unavailable()
    return planning, after
