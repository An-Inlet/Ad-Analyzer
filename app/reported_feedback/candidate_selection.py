"""Local operational-report selection after real owned catalog IO, no financial proof."""

from collections.abc import Callable
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.models import Campaign
from app.commerce.evidence import digest
from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.optimization_candidates.contracts import (
    CandidateEvidence,
    CandidateObservation,
    CandidateScope,
    SourceFence,
)
from app.optimization_candidates.selection_contracts import SelectionProvenance
from app.publication.coordinator import read_owned_outcome_receipt
from app.publication.optimization_contracts import MetaCurrentState
from app.reported_feedback.candidate_contracts import ReportedRulePolicyV1, ReportedRuleWorkV1
from app.reported_feedback.candidate_source import read_reported_rule
from app.reported_feedback.models import ReportedActionComparison


def select_reported_work(
    db: Session,
    principal: CustomerPrincipal,
    identity: IdentityProvider,
    scope: CandidateScope,
    policy: ReportedRulePolicyV1,
    state: MetaCurrentState,
    selection: SelectionProvenance,
    clock: Callable[[], datetime],
) -> ReportedRuleWorkV1:
    rows = list(
        db.scalars(
            select(ReportedActionComparison)
            .join(
                Campaign,
                (Campaign.id == ReportedActionComparison.campaign_id)
                & (Campaign.account_id == ReportedActionComparison.account_id),
            )
            .where(
                ReportedActionComparison.workspace_id == scope.account.workspace_id,
                ReportedActionComparison.account_id == scope.account.account.account_id,
                ReportedActionComparison.environment == policy.environment,
                Campaign.external_campaign_id == scope.target.external_id,
                ReportedActionComparison.expires_at > clock(),
            )
            .limit(2)
        )
    )
    # Never choose an older or more favorable original/comparison from ambiguous data.
    if len(rows) != 1:
        raise HTTPException(409, "current_reported_comparison_unavailable")
    row = rows[0]
    receipt = read_owned_outcome_receipt(
        db, scope.account.workspace_id, row.original_attempt_id, principal.user.id
    )
    if receipt is None or receipt.account != scope.account:
        raise HTTPException(409, "reported_original_receipt_unavailable")
    source = SourceFence.model_validate(
        {
            **scope.source.model_dump(mode="json"),
            "attempt_id": row.original_attempt_id,
            "receipt_id": receipt.receipt_id,
            "receipt_sequence": receipt.sequence,
            "receipt_digest": receipt.receipt_digest,
            "projection_digest": digest(
                ["inlet.owned-receipt.v1", receipt.model_dump(mode="json")]
            ),
        }
    )
    scope = CandidateScope.model_validate({**scope.model_dump(), "source": source})
    selection = SelectionProvenance.model_validate(
        {
            **selection.model_dump(),
            "scope_digest": scope.digest(),
        }
    )
    work = ReportedRuleWorkV1(
        scope=scope,
        policy=policy,
        selection=selection,
        comparison_id=row.id,
    )
    observed = CandidateObservation(
        scope=scope,
        state=state,
        evidence=CandidateEvidence(
            scope_digest=scope.digest(),
            source_schema="inlet.native-budget-observation.v1",
            source_digest=state.digest(),
            source_reference=source.publication_id,
            qualification="unqualified",
            direction="none",
            observed_at=selection.observed_at,
            expires_at=selection.expires_at,
        ),
    )
    read_reported_rule(db, principal, identity, work, observed, clock)
    return work
