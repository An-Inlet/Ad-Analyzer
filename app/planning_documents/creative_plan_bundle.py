"""Private genuine-v5 reporting and image envelope; no runtime registration."""

from datetime import UTC, datetime

from app.planning_documents.common import Frozen
from app.planning_documents.creative_image_collection import CollectedCreativeBasisV1
from app.planning_documents.ports import GenerationTicket
from app.planning_documents.selected_paired_evidence import SelectedPairedEvidenceV1
from app.planning_documents.selected_policy_contract import assert_selected_ticket_policy


def assert_creative_collection_time(
    collection: CollectedCreativeBasisV1,
    ticket: GenerationTicket,
    generated_at: datetime | None = None,
) -> None:
    collection = CollectedCreativeBasisV1.model_validate(collection)
    ticket = GenerationTicket.model_validate(ticket)
    collection.assert_ticket(ticket)
    prepared = ticket.prepared_at.astimezone(UTC)
    if any(image.observed_at.astimezone(UTC) < prepared for image in collection.basis.images):
        raise ValueError("creative inspection predates original ticket")
    if generated_at is not None:
        if (
            type(generated_at) is not datetime
            or generated_at.tzinfo is None
            or generated_at.utcoffset() is None
        ):
            raise ValueError("aware creative generation time required")
        instant = generated_at.astimezone(UTC)
        if instant < prepared or any(
            image.observed_at.astimezone(UTC) > instant for image in collection.basis.images
        ):
            raise ValueError("creative generation predates collected evidence")


class CreativePairedEvidenceV1(Frozen):
    reporting: SelectedPairedEvidenceV1
    creative: CollectedCreativeBasisV1

    def assert_ticket(self, supplied: GenerationTicket) -> None:
        current = type(self).model_validate(self)
        ticket = GenerationTicket.model_validate(supplied)
        contract = assert_selected_ticket_policy(ticket.policy_version, ticket.policy_digest)
        if not contract.requires_creative or ticket.inputs.selected_reporting is None:
            raise ValueError("genuine creative ticket and explicit selected inputs required")
        current.reporting.assert_ticket(ticket)
        assert_creative_collection_time(current.creative, ticket)
