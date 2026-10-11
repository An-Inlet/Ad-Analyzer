"""Original-session reporting and image collection; no runtime or persistence wiring."""

from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.campaign_review.contracts import MediaStore
from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.planning_documents.creative_basis_reader import OwnedPlanningImageReader
from app.planning_documents.creative_finalization import recheck_collected_creative
from app.planning_documents.creative_inputs import validate_creative_policy
from app.planning_documents.creative_plan_bundle import CreativePairedEvidenceV1
from app.planning_documents.creative_retained_proof import creative_proof_from_collection
from app.planning_documents.evidence_local import changed
from app.planning_documents.ports import GenerationTicket, PlanningCompositionPolicy
from app.planning_documents.read_context import PlanningReadContexts, snapshot
from app.planning_documents.selected_paired_local import recheck_selected_paired_sources
from app.planning_documents.selected_paired_reader import OwnedSelectedPairedReader
from app.planning_documents.selected_policy_contract import assert_selected_composition_policy


class OwnedCreativePairedReader:
    def __init__(
        self,
        sessions: Callable[[], Session],
        *,
        principal: CustomerPrincipal,
        provider: IdentityProvider,
        policy: PlanningCompositionPolicy,
        store: MediaStore,
        clock: Callable[[], datetime],
    ) -> None:
        self.sessions, self.principal = sessions, snapshot(principal)
        self.provider, self.policy, self.store, self.clock = provider, policy, store, clock

    def _now(self) -> datetime:
        now = self.clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise changed()
        return now.astimezone(UTC)

    def collect(self, supplied: GenerationTicket) -> CreativePairedEvidenceV1:
        ticket = GenerationTicket.model_validate(supplied)
        contract = assert_selected_composition_policy(
            self.policy,
            ticket_policy_version=ticket.policy_version,
            ticket_policy_digest=ticket.policy_digest,
        )
        validate_creative_policy(
            ticket.inputs.creative, contract.policy_version, contract.generator_version
        )
        if not contract.requires_creative or ticket.inputs.selected_reporting is None:
            raise changed()
        if (self.principal.user.id, self.principal.session.digest) != (
            ticket.actor_id,
            ticket.session_digest,
        ):
            raise HTTPException(401, "original customer session required")
        assert ticket.inputs.creative is not None
        reporting = OwnedSelectedPairedReader(
            self.sessions,
            principal=self.principal,
            provider=self.provider,
            policy=self.policy,
            clock=self._now,
        ).collect(ticket)
        creative = OwnedPlanningImageReader(
            self.sessions,
            principal=self.principal,
            provider=self.provider,
            store=self.store,
            clock=self._now,
        ).collect_pinned(ticket, ticket.inputs.creative)
        result = CreativePairedEvidenceV1(reporting=reporting, creative=creative)
        result.assert_ticket(ticket)
        expected = creative_proof_from_collection(creative, ticket)
        reads = PlanningReadContexts(
            self.sessions,
            self.principal,
            self.provider,
            ticket.inputs.workspace_id,
            ticket.actor_id,
        )
        with reads.open() as db:
            recheck_selected_paired_sources(
                db,
                principal=self.principal,
                ticket=ticket,
                bundle=reporting,
                authorize=reads.authorize,
                clock=self._now,
            )
            actual = recheck_collected_creative(
                db,
                principal=self.principal,
                ticket=ticket,
                collection=creative,
                now=self._now(),
                authorize=reads.authorize,
            )
            if actual != expected:
                raise changed()
            recheck_selected_paired_sources(
                db,
                principal=self.principal,
                ticket=ticket,
                bundle=reporting,
                authorize=reads.authorize,
                clock=self._now,
            )
        # Context exit performs original authority checks and may itself wait.
        # Retain original observation/expiry values; never renew their deadlines.
        result = CreativePairedEvidenceV1.model_validate(result)
        result.assert_ticket(ticket)
        refs = [c.reference for c in reporting.selected.catalogs]
        refs += [p.reference for p in reporting.selected.performance]
        refs += [c.reference for c in reporting.selected.context]
        refs += [p.reference for p in reporting.traffic]
        if reporting.selected.commerce is not None:
            refs.append(reporting.selected.commerce.reference)
        now = self._now()
        lower = [ticket.prepared_at, reporting.selected.collected_at]
        lower += [image.observed_at for image in creative.basis.images]
        lower += [ref.observed_at for ref in refs]
        if any(now < value.astimezone(UTC) for value in lower) or any(
            now >= ref.expires_at.astimezone(UTC) for ref in refs
        ):
            raise changed()
        return result
