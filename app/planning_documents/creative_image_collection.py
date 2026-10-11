"""Private image inspection envelope; never public evidence or finalization authority."""

from typing import TYPE_CHECKING

from pydantic import Field, field_validator, model_validator

from app.planning_documents.common import Digest, Frozen, Id
from app.planning_documents.creative_basis import CreativeBasisV1, OwnedPlanningImageV1, _ordered

if TYPE_CHECKING:
    from app.planning_documents.ports import GenerationTicket


class PlanningImageRowPinV1(Frozen):
    witness: OwnedPlanningImageV1
    created_by: Id

    def identity(self) -> dict[str, object]:
        current = type(self).model_validate(self)
        return dict(
            current.witness.model_dump(exclude={"observed_at"}), created_by=current.created_by
        )


class CollectedCreativeBasisV1(Frozen):
    basis: CreativeBasisV1
    rows: tuple[PlanningImageRowPinV1, ...] = Field(max_length=30)
    ticket_digest: Digest

    _order = field_validator("rows", mode="before")(_ordered)

    @model_validator(mode="after")
    def exact_rows(self) -> "CollectedCreativeBasisV1":
        if tuple(row.witness for row in self.rows) != self.basis.images:
            raise ValueError("complete ordered original image witnesses required")
        return self

    def assert_ticket(self, supplied: "GenerationTicket") -> None:
        from app.planning_documents.ports import GenerationTicket

        current = type(self).model_validate(self)
        ticket = GenerationTicket.model_validate(supplied)
        if (
            current.ticket_digest != ticket.digest()
            or ticket.inputs.creative is None
            or current.basis.requested != ticket.inputs.creative
            or current.basis.workspace_id != ticket.inputs.workspace_id
            or current.basis.goal_currency != ticket.inputs.goal.definition.target_window.currency
            or current.basis.privacy_revision != ticket.privacy_revision
        ):
            raise ValueError("exact original ticket and saved creative input required")
