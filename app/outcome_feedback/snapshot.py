"""Owned association consumer; no direction, execution authority or provider IO."""

from decimal import Decimal
from typing import Literal

from fastapi import HTTPException
from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commerce.evidence import digest
from app.outcome_feedback import service
from app.outcome_feedback.models import ContributionSlot, FeedbackRecord, V3Assessment
from app.outcomes.contracts import Code, Digest, Frozen, Positive
from app.outcomes.feedback import (
    FeedbackContribution,
    decision_policy_for,
    prepare_feedback,
    recompute_active_score,
)
from app.outcomes.maturity import MaturityScope, PolicyLookup, policy_for
from app.outcomes.owned import Clock
from app.outcomes.owned_v3 import OwnedV3Assessment, SessionAuthorize
from app.publication.execution_contracts import ExecutionAccount
from app.publication.execution_models import ProviderExecutionReview, ProviderExecutionRun
from app.publication.replacement_contracts import parse_review
from app.shopify.security import ShopifyError


class FeedbackScopeV1(Frozen):
    schema_version: Literal["inlet.feedback-scope.v1"] = "inlet.feedback-scope.v1"
    environment: Literal["contract_test", "live"]
    source: MaturityScope
    account: ExecutionAccount
    purpose: Literal["existing_campaign_optimize"]
    budget_owner_key: str = Field(min_length=1, max_length=256)
    target_set_digest: Digest
    target_digest: Digest
    operation: str = Field(min_length=1, max_length=64)
    before_days: Positive
    after_days: Positive

    @property
    def scope_digest(self) -> str:
        return digest(self.model_dump(mode="json"))


class ActiveContributionReference(Frozen):
    slot_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    revision: Positive
    original_attempt_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    feedback_digest: Digest
    assessment_digest: Digest
    assessed_at: AwareDatetime


class FeedbackSnapshotV1(Frozen):
    schema_version: Literal["inlet.feedback-snapshot.v1"] = "inlet.feedback-snapshot.v1"
    scope: FeedbackScopeV1
    family: Code
    policy_digest: Digest | None
    status: Literal["unavailable", "empty", "available"]
    reasons: tuple[Code, ...]
    score: Decimal | None = Field(ge=-1, le=1)
    contributions: tuple[ActiveContributionReference, ...] = Field(max_length=64)
    oldest_assessment_at: AwareDatetime | None
    newest_assessment_at: AwareDatetime | None
    interpretation: Literal["policy_weighted_association_not_causal"] = (
        "policy_weighted_association_not_causal"
    )
    count_interpretation: Literal["active_contributions_not_independent_observations"] = (
        "active_contributions_not_independent_observations"
    )
    spending_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def coherent(self) -> "FeedbackSnapshotV1":
        if self.status == "available":
            if (
                not self.contributions
                or self.score is None
                or self.reasons
                or self.policy_digest is None
            ):
                raise ValueError("available association requires bounded current contributions")
            dates = [c.assessed_at for c in self.contributions]
            if (self.oldest_assessment_at, self.newest_assessment_at) != (min(dates), max(dates)):
                raise ValueError("assessment range changed")
        elif (
            self.contributions
            or self.score is not None
            or not self.reasons
            or self.oldest_assessment_at
            or self.newest_assessment_at
        ):
            raise ValueError("empty/unavailable association cannot carry numeric evidence")
        if self.status == "empty" and self.policy_digest is None:
            raise ValueError("empty active set requires configured policy")
        if len({c.original_attempt_id for c in self.contributions}) != len(self.contributions):
            raise ValueError("duplicate original attempt")
        return self

    @property
    def snapshot_digest(self) -> str:
        return digest(self.model_dump(mode="json"))


def derive_scope(db: Session, value: OwnedV3Assessment) -> FeedbackScopeV1:
    """Only current read_current outputs; unsupported action families fail closed."""
    receipt = value.receipt
    run = db.get(ProviderExecutionRun, receipt.run_id, populate_existing=True)
    row = db.get(ProviderExecutionReview, run.review_id, populate_existing=True) if run else None
    if (
        receipt.purpose != "existing_campaign_optimize"
        or run is None
        or row is None
        or (
            run.workspace_id != value.context.scope.workspace_id
            or row.workspace_id != run.workspace_id
            or row.digest != receipt.review_digest
            or row.plan_digest != receipt.plan_digest
        )
    ):
        raise HTTPException(409, "supported owned optimization lineage required")
    document = parse_review(row.document)
    plan = document.plan
    if (
        document.digest() != row.digest
        or plan.digest() != row.plan_digest
        or plan.intent.scope != receipt.account
        or plan.intent.mandate != receipt.mandate
        or plan.intent.budget_owner.key(receipt.account) != receipt.budget_owner_key
        or plan.intent.approved_target_set_digest != receipt.target_set_digest
    ):
        raise HTTPException(409, "feedback original plan changed")
    return FeedbackScopeV1(
        environment=value.context.environment,
        source=value.context.scope,
        account=receipt.account,
        purpose="existing_campaign_optimize",
        budget_owner_key=receipt.budget_owner_key,
        target_set_digest=receipt.target_set_digest,
        target_digest=digest(plan.intent.target.model_dump(mode="json")),
        operation=plan.intent.action.kind,
        before_days=(value.before_window.end - value.before_window.start).days,
        after_days=(value.after_window.end - value.after_window.start).days,
    )


def _read_current(
    db: Session,
    wid: int,
    actor: str,
    assessment_id: str,
    authorize: SessionAuthorize,
    clock: Clock,
    policies: PolicyLookup,
) -> tuple[V3Assessment, OwnedV3Assessment]:
    try:
        return service.read_current(db, wid, actor, assessment_id, authorize, clock, policies)
    except ShopifyError:
        raise HTTPException(404, "owned feedback unavailable") from None


def apply_owned_feedback(
    db: Session,
    wid: int,
    actor: str,
    assessment_id: str,
    family: str,
    expected: service.SlotVersion | None,
    authorize: SessionAuthorize,
    clock: Clock,
    *,
    decisions: service.DecisionLookup = decision_policy_for,
    policies: PolicyLookup = policy_for,
) -> tuple[FeedbackScopeV1, ContributionSlot | None]:
    _, value = _read_current(db, wid, actor, assessment_id, authorize, clock, policies)
    scope = derive_scope(db, value)
    slot = service.apply_feedback(
        db,
        wid,
        actor,
        assessment_id,
        family,
        scope.scope_digest,
        expected,
        authorize,
        clock,
        decisions=decisions,
        policies=policies,
    )
    authorize(db)
    return scope, slot


def read_feedback_snapshot(
    db: Session,
    wid: int,
    actor: str,
    anchor_assessment_id: str,
    family: str,
    authorize: SessionAuthorize,
    clock: Clock,
    *,
    expected_scope: FeedbackScopeV1 | None = None,
    decisions: service.DecisionLookup = decision_policy_for,
    policies: PolicyLookup = policy_for,
) -> FeedbackSnapshotV1:
    """A real owned anchor fences even an empty group; never trust caller grouping keys."""
    _, anchor = _read_current(db, wid, actor, anchor_assessment_id, authorize, clock, policies)
    scope = derive_scope(db, anchor)
    if expected_scope is not None and expected_scope != scope:
        raise HTTPException(409, "feedback recommendation scope changed")
    decision = decisions(family)
    if decision is not None and decision.family != family:
        raise HTTPException(409, "feedback decision family changed")
    if decision is not None and (
        decision.metric_definition_digest,
        decision.currency,
        decision.time_zone,
    ) != (scope.source.metric_definition_digest, scope.source.currency, scope.source.time_zone):
        raise HTTPException(409, "feedback decision basis changed")
    references, values = [], []
    if decision is not None:
        rows = list(
            db.execute(
                select(ContributionSlot, FeedbackRecord)
                .join(
                    FeedbackRecord,
                    (FeedbackRecord.id == ContributionSlot.feedback_id)
                    & (FeedbackRecord.workspace_id == ContributionSlot.workspace_id),
                )
                .where(
                    ContributionSlot.workspace_id == wid,
                    ContributionSlot.environment == scope.environment,
                    ContributionSlot.policy_family == family,
                    ContributionSlot.scope_digest == scope.scope_digest,
                )
                .order_by(ContributionSlot.id)
                .limit(65)
            )
        )
        if len(rows) > 64:
            raise HTTPException(409, "active contribution read bound exceeded")
        for slot, row in rows:
            stored, value = _read_current(
                db, wid, actor, row.assessment_id, authorize, clock, policies
            )
            if derive_scope(db, value) != scope:
                raise HTTPException(409, "feedback contribution scope changed")
            contribution = FeedbackContribution.model_validate(row.document)
            calculated = prepare_feedback(
                value,
                decision,
                environment=scope.environment,
                expected_assessment_digest=stored.document_digest,
            )
            if (
                row.state != "eligible"
                or contribution != calculated
                or contribution.status != "eligible"
                or digest(contribution.model_dump(mode="json")) != row.document_digest
                or row.policy_digest != decision.policy_digest
                or row.assessment_digest != stored.document_digest
            ):
                raise HTTPException(409, "active contribution changed")
            values.append(contribution)
            references.append(
                ActiveContributionReference(
                    slot_id=slot.id,
                    revision=slot.revision,
                    original_attempt_id=value.receipt.attempt_id,
                    feedback_digest=row.document_digest,
                    assessment_digest=stored.document_digest,
                    assessed_at=value.context.evaluated_at,
                )
            )
    # Registries are local/pure; no policy change may survive this read transaction.
    if decisions(family) != decision:
        raise HTTPException(409, "feedback policy changed during read")
    authorize(db)
    dates = [item.assessed_at for item in references]
    return FeedbackSnapshotV1(
        scope=scope,
        family=family,
        policy_digest=decision.policy_digest if decision else None,
        status="unavailable" if decision is None else "available" if values else "empty",
        reasons=("decision_policy_unavailable",)
        if decision is None
        else ()
        if values
        else ("no_active_contributions",),
        score=recompute_active_score(
            decision, tuple(values), workspace_id=wid, environment=scope.environment
        )
        if values and decision
        else None,
        contributions=tuple(references),
        oldest_assessment_at=min(dates) if dates else None,
        newest_assessment_at=max(dates) if dates else None,
    )
