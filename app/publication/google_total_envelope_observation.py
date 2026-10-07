"""Owned joins of original native configuration and a current diagnostic observation."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collectors.google_native_inventory import GoogleNativeInventory
from app.publication import coordinator, customer_intents, google_execution_completion
from app.publication.contracts import fingerprint
from app.publication.coordinator_contracts import CreationExecutionReview
from app.publication.execution_authorization import ExecutionAuthorizer
from app.publication.execution_contracts import ExecutionAccount, ProviderMandatePolicy
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionConsent,
    ProviderExecutionReview,
    ProviderExecutionRevision,
    ProviderExecutionRun,
    ProviderExposureReservation,
)
from app.publication.google_total_envelope_contracts import (
    EnvelopeReason,
    GoogleTotalEnvelopeViewV1,
)
from app.publication.provider_contracts import (
    BoundProviderRequest,
    GoogleCreatePausedCampaign,
    GoogleCreateTotalBudget,
    GoogleSearchTotalPublicationFields,
    ProviderPublishPlan,
)


@dataclass(frozen=True)
class OriginalTotalEnvelopeBinding:
    account: ExecutionAccount
    review: CreationExecutionReview
    policy: ProviderMandatePolicy
    budget_resource: str
    campaign_resource: str
    campaign: GoogleCreatePausedCampaign
    original_total: int
    native_time_zone: str
    reservation_amount: int
    reservation_state: str
    commitment: str
    run_id: str


def bind_owned_original_total_envelope(
    db: Session,
    workspace_id: int,
    run_id: str,
    actor: str,
    *,
    authorize: ExecutionAuthorizer,
    clock: Callable[[], datetime],
) -> OriginalTotalEnvelopeBinding:
    authorize(db, workspace_id, actor)
    run = db.scalar(
        select(ProviderExecutionRun).where(
            ProviderExecutionRun.id == run_id,
            ProviderExecutionRun.workspace_id == workspace_id,
        )
    )
    if run is None:
        raise HTTPException(404, "Execution run unavailable.")
    raw = db.get(ProviderExecutionReview, run.review_id)
    if raw is None or raw.document.get("purpose") != "create_paused":
        raise HTTPException(409, "Original total-budget creation is unavailable.")
    review = CreationExecutionReview.model_validate(raw.document)
    if (
        not isinstance(review.plan, ProviderPublishPlan)
        or not isinstance(review.plan.review.configuration, GoogleSearchTotalPublicationFields)
        or raw.workspace_id != workspace_id
        or raw.digest != review.digest()
        or raw.plan_digest != review.plan.digest()
    ):
        raise HTTPException(409, "Original total-budget creation is unavailable.")
    account = ExecutionAccount.from_publication(review.plan.review.scope)
    if customer_intents.account(db, workspace_id, account.account.account_id) != account:
        raise HTTPException(409, "The original advertising connection has changed.")
    revision = db.get(
        ProviderExecutionRevision, (review.mandate.mandate_id, review.mandate.revision)
    )
    consent = db.get(ProviderExecutionConsent, review.mandate.consent_id)
    reservation = db.get(ProviderExposureReservation, run.reservation_id)
    if (
        revision is None
        or revision.workspace_id != workspace_id
        or consent is None
        or consent.workspace_id != workspace_id
        or consent.mandate_id != review.mandate.mandate_id
        or consent.revision != review.mandate.revision
        or consent.policy_digest != review.mandate.policy_digest
        or reservation is None
        or reservation.workspace_id != workspace_id
        or reservation.environment != review.mandate.environment
        or reservation.ledger_id != review.mandate.ledger_id
    ):
        raise HTTPException(409, "Original allocation evidence is unavailable.")
    policy = ProviderMandatePolicy.model_validate(revision.policy)
    if (
        policy.digest() != revision.digest
        or revision.digest != review.mandate.policy_digest
        or policy.environment != review.mandate.environment
        or policy.workspace_id != workspace_id
        or account not in policy.accounts
    ):
        raise HTTPException(409, "Original allocation evidence has changed.")
    evidence: list[dict[str, str]] = []
    resources: dict[str, str] = {}
    campaign: GoogleCreatePausedCampaign | None = None
    for step in ("budget", "campaign"):
        attempts = list(
            db.scalars(
                select(ProviderExecutionAttempt)
                .where(
                    ProviderExecutionAttempt.workspace_id == workspace_id,
                    ProviderExecutionAttempt.run_id == run_id,
                    ProviderExecutionAttempt.step_id == step,
                )
                .limit(2)
            )
        )
        if len(attempts) != 1:
            raise HTTPException(409, "Original creation completion is unavailable.")
        attempt = attempts[0]
        _, bound_review, _, request = coordinator.evidence_lock(db, workspace_id, attempt.id)
        completion = google_execution_completion.read_execution_completion(
            db,
            workspace_id,
            attempt.id,
            actor,
            authorize=lambda: authorize(db, workspace_id, actor),
            clock=clock,
        )
        receipt = coordinator.read_owned_outcome_receipt(db, workspace_id, attempt.id, actor)
        if (
            not isinstance(request, BoundProviderRequest)
            or bound_review != review
            or completion.status != "completed"
            or receipt is None
            or receipt.resource_name is None
        ):
            raise HTTPException(409, "Original creation completion is unavailable.")
        if step == "budget":
            if not isinstance(request.step.operation, GoogleCreateTotalBudget):
                raise HTTPException(409, "Original total-budget request is unavailable.")
        else:
            operation = request.step.operation
            if (
                not isinstance(operation, GoogleCreatePausedCampaign)
                or operation.budget.step_id != "budget"
                or request.resources.get("budget") != resources["budget"]
            ):
                raise HTTPException(409, "Original campaign budget binding changed.")
            campaign = operation
        resources[step] = receipt.resource_name
        evidence.append(
            {
                "attempt": attempt.id,
                "request": request.digest(),
                "receipt": fingerprint(
                    "inlet.normalized-provider-receipt.v1", receipt.model_dump(mode="json")
                ),
                "completion": completion.commitment or "",
            }
        )
    assert campaign is not None
    configuration = review.plan.review.configuration
    if policy.currency != review.plan.review.source.definition.currency:
        raise HTTPException(409, "Original currency or timezone changed.")
    commitment = fingerprint(
        "inlet.original-total-envelope-binding.v1",
        {
            "run": run_id,
            "review": review.digest(),
            "policy": policy.digest(),
            "evidence": evidence,
            "resources": resources,
            "reservation": {
                "id": reservation.id,
                "amount": reservation.amount_micros,
                "state": reservation.state,
                "ledger": reservation.ledger_id,
            },
        },
    )
    authorize(db, workspace_id, actor)
    return OriginalTotalEnvelopeBinding(
        account,
        review,
        policy,
        resources["budget"],
        resources["campaign"],
        campaign,
        configuration.total_budget_micros,
        configuration.account_timezone,
        reservation.amount_micros,
        reservation.state,
        commitment,
        run_id,
    )


def observe_total_envelope(
    original: OriginalTotalEnvelopeBinding,
    inventory: GoogleNativeInventory,
    *,
    now: datetime,
    expires_at: datetime,
) -> GoogleTotalEnvelopeViewV1:
    if (
        inventory.request.account != original.account
        or inventory.request.currency != original.policy.currency
        or inventory.request.time_zone != original.native_time_zone
        or now >= min(inventory.expires_at, expires_at)
    ):
        raise HTTPException(409, "The observation expired or its account changed.")
    reasons: list[EnvelopeReason] = [
        "financial_basis_unqualified",
        "historical_liabilities_unverified",
    ]
    budgets = [b for b in inventory.campaign_budgets if b.resource_name == original.budget_resource]
    campaigns = [c for c in inventory.campaigns if c.resource_name == original.campaign_resource]
    observed = budgets[0].total_amount_micros if len(budgets) == 1 else None
    if not inventory.advertising_inventory_read_complete:
        reasons.append("native_inventory_incomplete")
    if len(budgets) != 1 or len(campaigns) != 1:
        reasons.append("native_resource_unavailable")
    else:
        budget, campaign = budgets[0], campaigns[0]
        owners = [
            c
            for c in inventory.campaigns
            if c.budget_resource == budget.resource_name and c.status != "REMOVED"
        ]
        if (
            budget.explicitly_shared
            or budget.reference_count != 1
            or len(owners) != 1
            or owners[0].resource_name != campaign.resource_name
            or campaign.budget_resource != budget.resource_name
        ):
            reasons.append("native_ownership_changed")
        if (
            budget.period != "CUSTOM_PERIOD"
            or budget.type != "STANDARD"
            or budget.status != "ENABLED"
            or budget.amount_micros not in (None, 0)
            or observed != original.original_total
        ):
            reasons.append("native_budget_changed")
        if (
            campaign.channel != "SEARCH"
            or campaign.bidding_strategy != "MANUAL_CPC"
            or campaign.status not in {"ENABLED", "PAUSED"}
            or campaign.start_date_time != original.campaign.starts_local
            or campaign.end_date_time != original.campaign.ends_local
        ):
            reasons.append("native_campaign_changed")
    unavailable = (
        "native_resource_unavailable" in reasons or "native_inventory_incomplete" in reasons
    )
    definition = original.review.plan.review.source.definition
    return GoogleTotalEnvelopeViewV1(
        run_id=original.run_id,
        environment=original.policy.environment,
        status="unavailable"
        if unavailable
        else "configuration_drift"
        if len(reasons) > 2
        else "matching_configuration",
        currency=original.policy.currency,
        time_zone=original.native_time_zone,
        campaign_starts_at=definition.starts_at,
        campaign_ends_at=definition.ends_at,
        original_total_micros=original.original_total,
        observed_total_micros=observed,
        reservation_micros=original.reservation_amount,
        reservation_state=original.reservation_state,
        original_binding_digest=original.commitment,
        inventory_digest=inventory.digest(),
        observation_started_at=inventory.observation_started_at,
        observed_at=inventory.observed_at,
        expires_at=min(expires_at, inventory.expires_at),
        reasons=reasons,
    )
