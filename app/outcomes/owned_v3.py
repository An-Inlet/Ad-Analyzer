"""Read-only owned association bridge with no locks held across producer IO.

V2 persistence and history remain untouched. Production source/policy registries
are disabled; genuine independent reconciliation and timing producers are missing.
"""

from collections.abc import Callable
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Literal

from fastapi import HTTPException
from pydantic import Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commerce.evidence import digest, lock_workspace
from app.commerce.ledger import DEFINITION
from app.commerce.publication_contracts import version_filter
from app.goals.models import Goal, GoalRevision
from app.goals.schemas import GoalDefinition
from app.outcomes.contracts import Code, Digest, Frozen, Window
from app.outcomes.descriptive import validate_manifest
from app.outcomes.maturity import (
    IndependentReconciliationEvidence,
    MaturityContext,
    MaturityScope,
    OperationalMaturityPolicy,
    OperationalMaturityResult,
    PolicyLookup,
    ProducerLookup,
    evaluate_operational_maturity,
    policy_for,
    producer_for,
)
from app.outcomes.owned import Clock, now, publication
from app.publication.coordinator import read_owned_outcome_receipt
from app.publication.execution_contracts import NormalizedProviderReceipt
from app.publication.execution_mandates import current_account
from app.shopify.security import ShopifyError, utc


class OwnedV3Request(Frozen):
    attempt_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    publication_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    before_start: date
    before_end: date
    after_start: date
    after_end: date

    @model_validator(mode="after")
    def bounded(self) -> "OwnedV3Request":
        if not (
            self.before_start < self.before_end <= self.after_start < self.after_end
            and (self.after_end - self.before_start).days <= 400
        ):
            raise ValueError("invalid bounded observation windows")
        return self


class OwnedV3Assessment(Frozen):
    schema_version: Literal["inlet.owned-outcome-assessment.v3"] = (
        "inlet.owned-outcome-assessment.v3"
    )
    context: MaturityContext
    receipt: NormalizedProviderReceipt
    publication_id: str
    publication_digest: Digest
    input_digest: Digest
    before_window: Window
    after_window: Window
    before_maturity: OperationalMaturityResult | None
    after_maturity: OperationalMaturityResult | None
    status: Literal["operational_association_as_of", "insufficient"]
    reasons: tuple[Code, ...]
    before_value_micros: Decimal | None
    after_value_micros: Decimal | None
    absolute_difference_micros: Decimal | None
    relative_difference: Decimal | None
    warnings: tuple[Code, ...]
    causal_lift: None = None
    recommendation_update: None = None
    spending_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def honest_status(self) -> "OwnedV3Assessment":
        if self.status == "insufficient":
            if not self.reasons or any(
                value is not None
                for value in (
                    self.before_value_micros,
                    self.after_value_micros,
                    self.absolute_difference_micros,
                    self.relative_difference,
                )
            ):
                raise ValueError("insufficient assessment cannot claim differences")
        elif (
            self.reasons
            or self.before_maturity is None
            or self.after_maturity is None
            or any(
                value.status != "operational_as_of" or value.environment != self.context.environment
                for value in (self.before_maturity, self.after_maturity)
            )
            or self.receipt.effective_time_evidence != "authoritative_interval"
            or self.receipt.outcome != "verified_effect"
            or self.receipt.purpose == "create_paused"
            or self.receipt.environment != self.context.environment
            or self.receipt.account.workspace_id != self.context.scope.workspace_id
            or self.receipt.goal_id != self.context.scope.goal_id
            or self.receipt.goal_revision != self.context.scope.goal_revision
            or not self.context.source_current
            or self.before_value_micros is None
            or self.after_value_micros is None
            or self.absolute_difference_micros is None
            or self.before_maturity.policy_digest != self.after_maturity.policy_digest
            or any(
                value.context_digest != digest(self.context.model_dump(mode="json"))
                for value in (self.before_maturity, self.after_maturity)
            )
        ):
            raise ValueError("association requires qualified observations and timing")
        return self


class OwnedSnapshot(Frozen):
    context: MaturityContext
    receipt: NormalizedProviderReceipt
    publication_id: str
    publication_digest: Digest


def compare_owned_v3(
    snapshot: OwnedSnapshot,
    request: OwnedV3Request,
    policy: OperationalMaturityPolicy | None,
    before: IndependentReconciliationEvidence | None,
    after: IndependentReconciliationEvidence | None,
) -> OwnedV3Assessment:
    """Pure reusable bridge. Caller must supply a freshly revalidated owned snapshot."""
    snapshot = OwnedSnapshot.model_validate(snapshot.model_dump())
    request = OwnedV3Request.model_validate(request.model_dump())
    context, receipt = snapshot.context, snapshot.receipt
    windows = (
        Window.local(request.before_start, request.before_end, context.scope.time_zone),
        Window.local(request.after_start, request.after_end, context.scope.time_zone),
    )
    reasons: set[str] = set()
    if (
        receipt.account.workspace_id != context.scope.workspace_id
        or receipt.goal_id != context.scope.goal_id
        or receipt.goal_revision != context.scope.goal_revision
        or receipt.environment != context.environment
        or receipt.attempt_id != request.attempt_id
        or snapshot.publication_id != request.publication_id
    ):
        reasons.add("receipt_scope_mismatch")
    if receipt.purpose == "create_paused":
        reasons.add("activation_unverified")
    if receipt.outcome != "verified_effect":
        reasons.add("action_effect_unverified")
    if receipt.observed_at > context.evaluated_at:
        reasons.add("future_receipt")
    if receipt.effective_time_evidence != "authoritative_interval":
        reasons.add("effective_time_unknown")
    elif (
        receipt.effective_lower is None
        or receipt.effective_upper is None
        or windows[0].end_utc > receipt.effective_lower
        or windows[1].start_utc < receipt.effective_upper
    ):
        reasons.add("windows_overlap_effect_interval")
    if (request.before_end - request.before_start) != (request.after_end - request.after_start):
        reasons.add("unequal_local_days")
    if any(window.end_utc > context.evaluated_at for window in windows):
        reasons.add("window_not_closed")
    if not context.source_current:
        reasons.add("source_not_current")
    if policy is None:
        reasons.add("maturity_policy_unavailable")
    results: list[OperationalMaturityResult | None] = []
    for evidence, window in zip((before, after), windows, strict=True):
        if evidence is None:
            reasons.add("independent_producer_unavailable")
            results.append(None)
            continue
        evidence = IndependentReconciliationEvidence.model_validate(evidence.model_dump())
        if (evidence.start, evidence.end) != (window.start, window.end):
            reasons.add("producer_window_mismatch")
        result = evaluate_operational_maturity(policy, evidence, context)
        results.append(result)
        reasons.update(result.reasons)
    if before is not None and after is not None and before.observations and after.observations:
        left, right = before.observations[-1], after.observations[-1]
        if (left.observed_at, left.fresh_through) != (right.observed_at, right.fresh_through):
            reasons.add("unequal_observation_as_of")
    before_value = after_value = absolute = relative = None
    warnings = {
        "association_not_causal_lift",
        "store_total_not_ad_attribution",
        "confounder_coverage_unknown",
        "future_corrections_possible",
    }
    if context.environment == "contract_test":
        warnings.add("contract_test_only")
    if not reasons and before is not None and after is not None:
        before_value = Decimal(
            sum(
                day.value_micros
                for day in before.observations[-1].days
                if day.value_micros is not None
            )
        )
        after_value = Decimal(
            sum(
                day.value_micros
                for day in after.observations[-1].days
                if day.value_micros is not None
            )
        )
        with localcontext() as decimal_context:
            decimal_context.prec = 60
            decimal_context.rounding = ROUND_HALF_EVEN
            absolute = Decimal(int(after_value) - int(before_value))
            if before_value > 0:
                relative = absolute / before_value
            else:
                warnings.add("baseline_zero" if before_value == 0 else "baseline_negative")
    return OwnedV3Assessment(
        context=context,
        receipt=receipt,
        publication_id=snapshot.publication_id,
        publication_digest=snapshot.publication_digest,
        input_digest=digest(
            [
                "inlet.owned-v3-input.v1",
                snapshot.model_dump(mode="json"),
                request.model_dump(mode="json"),
                policy.model_dump(mode="json") if policy else None,
                [result.model_dump(mode="json") if result else None for result in results],
            ]
        ),
        before_window=windows[0],
        after_window=windows[1],
        before_maturity=results[0],
        after_maturity=results[1],
        status="insufficient" if reasons else "operational_association_as_of",
        reasons=tuple(sorted(reasons)),
        before_value_micros=before_value,
        after_value_micros=after_value,
        absolute_difference_micros=absolute,
        relative_difference=relative,
        warnings=tuple(sorted(warnings)),
    )


SessionFactory = Callable[[], Session]
SessionAuthorize = Callable[[Session], None]


def _snapshot(
    db: Session,
    wid: int,
    actor: str,
    request: OwnedV3Request,
    authorize: SessionAuthorize,
    clock: Clock,
) -> OwnedSnapshot:
    try:
        lock_workspace(db, wid, active=True)
    except ShopifyError:
        raise HTTPException(404, "workspace unavailable") from None
    authorize(db)
    receipt = read_owned_outcome_receipt(db, wid, request.attempt_id, actor)
    if receipt is None:
        raise HTTPException(409, "owned receipt unavailable")
    current_account(db, receipt.account)
    row, store = publication(db, wid, request.publication_id, clock)
    validate_manifest(row)
    latest = db.scalar(
        select(type(row).id)
        .where(type(row).workspace_id == wid, type(row).store_id == store.id, version_filter())
        .order_by(type(row).publication_revision.desc())
        .limit(1)
    )
    if latest != row.id:
        raise HTTPException(409, "latest publication changed")
    goal = db.scalar(
        select(Goal)
        .where(Goal.id == receipt.goal_id, Goal.workspace_id == wid)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if goal is None or goal.revision != receipt.goal_revision:
        raise HTTPException(409, "current goal changed")
    revision = db.get(GoalRevision, (goal.id, goal.revision), populate_existing=True)
    if revision is None or revision.workspace_id != wid or revision.confirmed_at is None:
        raise HTTPException(409, "confirmed goal unavailable")
    definition = GoalDefinition.model_validate(revision.definition)
    if (
        definition.store_id,
        definition.target_window.currency,
        definition.target_window.time_zone,
    ) != (store.id, store.currency, store.time_zone):
        raise HTTPException(409, "goal source mismatch")
    authorize(db)
    publication(db, wid, request.publication_id, clock)
    if utc(row.published_at) > utc(clock()):
        raise HTTPException(409, "future source evidence unavailable")
    context = MaturityContext(
        environment=receipt.environment,
        evaluated_at=utc(clock()),
        source_current=store.status == "active"
        and store.window_end is None
        and row.source_revision == store.revision,
        scope=MaturityScope(
            workspace_id=wid,
            store_id=store.id,
            generation=row.generation,
            privacy_epoch=row.privacy_epoch,
            goal_id=goal.id,
            goal_revision=goal.revision,
            goal_digest=digest(definition.model_dump(mode="json")),
            metric_definition_digest=digest(DEFINITION),
            currency=store.currency,
            time_zone=store.time_zone,
        ),
    )
    return OwnedSnapshot(
        context=context,
        receipt=receipt,
        publication_id=row.id,
        publication_digest=row.manifest_digest,
    )


def assess_owned_v3(
    sessions: SessionFactory,
    wid: int,
    actor: str,
    request: OwnedV3Request,
    authorize: SessionAuthorize,
    clock: Clock = now,
    *,
    policies: PolicyLookup = policy_for,
    producers: ProducerLookup = producer_for,
) -> OwnedV3Assessment:
    """Own both short-lived transactions; never commit a caller-owned transaction."""
    request = OwnedV3Request.model_validate(request.model_dump())
    with sessions() as db:
        initial = _snapshot(db, wid, actor, request, authorize, clock)
    # The owned session has closed and released every DB lock before producer IO.
    policy, producer = policies(initial.context.scope), producers(initial.context.scope)
    before = after = None
    if policy is not None and producer is not None:
        before = producer(initial.context, request.before_start, request.before_end)
        after = producer(initial.context, request.after_start, request.after_end)
    with sessions() as db:
        current = _snapshot(db, wid, actor, request, authorize, clock)
        if (
            current.context.scope != initial.context.scope
            or current.context.environment != initial.context.environment
            or current.context.source_current != initial.context.source_current
            or current.receipt != initial.receipt
            or current.publication_digest != initial.publication_digest
            or current.context.evaluated_at < initial.context.evaluated_at
            or policies(current.context.scope) != policy
        ):
            raise HTTPException(409, "owned outcome evidence changed")
        result = compare_owned_v3(current, request, policy, before, after)
        authorize(db)
        publication(db, wid, request.publication_id, clock)
        return result
