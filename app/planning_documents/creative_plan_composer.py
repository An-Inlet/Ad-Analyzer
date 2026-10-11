"""Genuine pure creative document composition; unavailable to runtime services."""

from datetime import UTC, datetime
from decimal import Context, localcontext

from app.planning_documents.composer import PlanCompositionUnavailable
from app.planning_documents.creative_plan_bundle import (
    CreativePairedEvidenceV1,
    assert_creative_collection_time,
)
from app.planning_documents.documents import PlanVersion
from app.planning_documents.google_budget_generation_guard import reject_google_budget_generation
from app.planning_documents.ports import GenerationTicket, PlanningCompositionPolicy
from app.planning_documents.selected_composer import SelectedPlanComposer
from app.planning_documents.selected_policy_contract import assert_selected_composition_policy


class CreativePlanComposer:
    def compose(
        self,
        *,
        ticket: GenerationTicket,
        evidence: CreativePairedEvidenceV1,
        policy: PlanningCompositionPolicy,
        generated_at: datetime,
    ) -> PlanVersion:
        try:
            if type(generated_at) is not datetime:
                raise ValueError("aware creative generation time required")
            ticket = GenerationTicket.model_validate(ticket)
            reject_google_budget_generation(ticket.inputs.google_daily_budget_intents)
            evidence = CreativePairedEvidenceV1.model_validate(evidence)
            policy = PlanningCompositionPolicy.model_validate(policy)
            contract = assert_selected_composition_policy(
                policy,
                ticket_policy_version=ticket.policy_version,
                ticket_policy_digest=ticket.policy_digest,
            )
            if not contract.requires_creative or contract.requires_owner_review:
                raise ValueError("exact canonical creative policy required")
            evidence.assert_ticket(ticket)
            assert_creative_collection_time(evidence.creative, ticket, generated_at)
            with localcontext(Context(prec=50)):
                return SelectedPlanComposer()._compose(
                    ticket,
                    evidence.reporting,
                    policy,
                    generated_at.astimezone(UTC),
                    creative=evidence.creative,
                )
        except ValueError as error:
            raise PlanCompositionUnavailable(str(error)) from error
