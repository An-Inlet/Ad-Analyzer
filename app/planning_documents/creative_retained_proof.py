"""Immutable creative commitments; parsing grants no ownership or write authority."""

from datetime import datetime
from typing import TYPE_CHECKING, Literal

from pydantic import Field, field_validator, model_validator

from app.planning_documents.common import Digest, Id, NoAuthority, fingerprint
from app.planning_documents.creative_basis import CreativeBasisV1, _ordered

if TYPE_CHECKING:
    from app.planning_documents.context import PlanInputRevision
    from app.planning_documents.creative_image_collection import (
        CollectedCreativeBasisV1,
        PlanningImageRowPinV1,
    )
    from app.planning_documents.ports import GenerationTicket


class CreativeImageCommitmentV1(NoAuthority):
    media_id: Id
    row_identity_digest: Digest


class CreativeRetainedProofV1(NoAuthority):
    schema_version: Literal["inlet.creative-retained-proof.v1"] = "inlet.creative-retained-proof.v1"
    basis: CreativeBasisV1
    images: tuple[CreativeImageCommitmentV1, ...] = Field(max_length=30)

    _order = field_validator("images", mode="before")(_ordered)

    @model_validator(mode="after")
    def exact(self) -> "CreativeRetainedProofV1":
        if tuple(item.media_id for item in self.images) != tuple(
            image.media_id for image in self.basis.images
        ):
            raise ValueError("complete ordered image commitments required")
        return self

    def assert_inputs(self, inputs: "PlanInputRevision", privacy_revision: int) -> None:
        from app.planning_documents.context import PlanInputRevision

        current = type(self).model_validate(self)
        inputs = PlanInputRevision.model_validate(inputs)
        if type(privacy_revision) is not int or privacy_revision < 0:
            raise ValueError("strict nonnegative privacy revision required")
        if (
            inputs.creative is None
            or inputs.creative != current.basis.requested
            or inputs.workspace_id != current.basis.workspace_id
            or inputs.goal.definition.target_window.currency != current.basis.goal_currency
            or privacy_revision != current.basis.privacy_revision
        ):
            raise ValueError("exact saved creative input and scope required")

    def source_binding_digest(self) -> str:
        current = type(self).model_validate(self)
        return fingerprint(
            "creative-source-binding.v1",
            dict(
                schema_version=current.schema_version,
                workspace_id=current.basis.workspace_id,
                privacy_revision=current.basis.privacy_revision,
                requested_digest=current.basis.requested.digest(),
                images=[image.model_dump(mode="json") for image in current.images],
            ),
        )


def creative_proof_from_collection(
    collection: "CollectedCreativeBasisV1", ticket: "GenerationTicket"
) -> CreativeRetainedProofV1:
    from app.planning_documents.creative_image_collection import CollectedCreativeBasisV1
    from app.planning_documents.ports import GenerationTicket

    collection = CollectedCreativeBasisV1.model_validate(collection)
    ticket = GenerationTicket.model_validate(ticket)
    collection.assert_ticket(ticket)
    result = CreativeRetainedProofV1(
        basis=collection.basis,
        images=tuple(
            CreativeImageCommitmentV1(
                media_id=row.witness.media_id,
                row_identity_digest=creative_image_row_identity_digest(row),
            )
            for row in collection.rows
        ),
    )
    result.assert_inputs(ticket.inputs, ticket.privacy_revision)
    return result


def creative_image_row_identity_digest(row: "PlanningImageRowPinV1") -> str:
    """Exact original commitment; excludes observation time only, never creator/time."""
    from app.planning_documents.creative_image_collection import PlanningImageRowPinV1

    row = PlanningImageRowPinV1.model_validate(row)
    return fingerprint(
        "creative-image-row-identity.v1",
        {
            key: value.isoformat() if isinstance(value, datetime) else value
            for key, value in row.identity().items()
        },
    )
