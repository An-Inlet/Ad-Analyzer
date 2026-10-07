"""Strict retained origin binding; this local reader grants no provider qualification."""

from collections.abc import Callable

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.production_runtime.optimization_origin_contracts import OptimizationMandatePreparationV1
from app.production_runtime.optimization_origin_models import OptimizationMandatePreparationRow
from app.publication.execution_contracts import ProviderMandatePolicy
from app.publication.execution_models import ProviderExecutionRevision

OriginFactory = Callable[[str, int], OptimizationMandatePreparationV1]
OriginGuard = Callable[[Session, ProviderExecutionRevision, ProviderMandatePolicy], None]


def unavailable() -> HTTPException:
    return HTTPException(409, "optimization_mandate_origin_unavailable")


def validate_policy(
    document: OptimizationMandatePreparationV1, policy: ProviderMandatePolicy
) -> None:
    intent, operating = document.intent, document.operating_policy
    rule = operating.rule(intent.aggressiveness)
    cap = min(intent.total_cap_micros, rule.per_plan_cap_micros)
    if (
        document.provider_policy_digest != policy.digest()
        or document.workspace_id != policy.workspace_id
        or document.environment != policy.environment
        or intent.selection.goal_id != policy.goal_id
        or intent.selection.goal_revision != policy.goal_revision
        or len(policy.accounts) != 1
        or policy.accounts[0].account.account_id != intent.selection.account_id
        or policy.accounts[0].digest() != document.account_scope_digest
        or policy.allowed_target_set_digest != document.target_set_digest
        or policy.allowed_purposes != ["existing_campaign_optimize"]
        or policy.currency != operating.currency
        or policy.total_cap_micros != intent.total_cap_micros
        or policy.per_plan_cap_micros != cap
        or policy.positive_change_cap_micros != min(cap, rule.positive_change_cap_micros)
        or policy.action_limit != rule.action_limit
        or policy.cooldown_seconds != rule.cooldown_seconds
        or policy.freshness_seconds != rule.freshness_seconds
        or policy.aggressiveness_percent != rule.aggressiveness_percent
    ):
        raise unavailable()


def read(
    db: Session, revision: ProviderExecutionRevision, policy: ProviderMandatePolicy
) -> OptimizationMandatePreparationV1 | None:
    if revision.origin_kind == "legacy" and revision.origin_preparation_digest is None:
        return None
    if revision.origin_kind != "optimization_customer_v1":
        raise unavailable()
    row = db.get(
        OptimizationMandatePreparationRow,
        (revision.mandate_id, revision.revision),
        populate_existing=True,
    )
    if row is None:
        raise unavailable()
    try:
        document = OptimizationMandatePreparationV1.model_validate(row.document)
    except (ValidationError, TypeError, ValueError):
        raise unavailable() from None
    if (
        row.workspace_id != revision.workspace_id
        or row.provider_policy_digest != revision.digest
        or row.preparation_digest != revision.origin_preparation_digest
        or document.digest() != row.preparation_digest
        or document.mandate_id != revision.mandate_id
        or document.mandate_revision != revision.revision
    ):
        raise unavailable()
    validate_policy(document, policy)
    return document


def forward(
    db: Session,
    revision: ProviderExecutionRevision,
    policy: ProviderMandatePolicy,
    guard: OriginGuard | None,
) -> None:
    document = read(db, revision, policy)
    if document is not None and guard is None:
        raise unavailable()
    if guard is not None:
        # A configured guard also rejects legacy revisions; legacy isn't an escape
        # from an explicitly configured customer origin requirement.
        guard(db, revision, policy)
