"""Finite exact customer-instruction interpretation, not approval or semantic inference."""

from typing import TYPE_CHECKING, Literal

from pydantic import Field, model_validator

from app.planning_documents.common import Digest, Frozen, NoAuthority, Text

if TYPE_CHECKING:
    from app.planning_documents.context import PlanInputRevision

LITERAL = "No discount claims."
OBLIGATIONS = (
    "Use fixed neutral public copy; do not interpolate product names or asserted facts.",
    "Omit price, savings, discount and promotional offers from suggested public copy.",
    "Inspect image pixels, video, audio and destinations separately before customer approval.",
)
UNRESOLVED = "Clarify this restriction; its meaning is not covered by the exact supported rule."


class ConstraintEntryV1(Frozen):
    source_index: int = Field(strict=True, ge=0, lt=30)
    original_text: Text
    rule: Literal["exclude_discount_claims"] | None
    unresolved_reason: Text | None

    @model_validator(mode="after")
    def exact(self) -> "ConstraintEntryV1":
        expected = (
            ("exclude_discount_claims", None)
            if self.original_text == LITERAL
            else (None, UNRESOLVED)
        )
        if (self.rule, self.unresolved_reason) != expected:
            raise ValueError("exact finite constraint interpretation required")
        return self


def _entries(texts: tuple[str, ...]) -> tuple[ConstraintEntryV1, ...]:
    return tuple(
        ConstraintEntryV1(
            source_index=i,
            original_text=text,
            rule="exclude_discount_claims" if text == LITERAL else None,
            unresolved_reason=None if text == LITERAL else UNRESOLVED,
        )
        for i, text in enumerate(texts)
    )


class ConstraintInterpretationV1(NoAuthority):
    schema_version: Literal["inlet.constraint-interpretation.v1"] = (
        "inlet.constraint-interpretation.v1"
    )
    input_digest: Digest
    original_constraints: tuple[Text, ...] = Field(max_length=30)
    entries: tuple[ConstraintEntryV1, ...] = Field(max_length=30)
    # Product restrictions are a separate explicit source; never silently treated as approved.
    original_product_restrictions: tuple[Text, ...] = Field(max_length=20)
    product_entries: tuple[ConstraintEntryV1, ...] = Field(max_length=20)
    disposition: Literal["no_constraints", "fully_recognized", "unresolved"]
    obligations: tuple[Text, ...] = Field(max_length=3)
    provenance: Literal["customer_instruction_only"] = "customer_instruction_only"

    @model_validator(mode="after")
    def coherent(self) -> "ConstraintInterpretationV1":
        entries, product = (
            _entries(self.original_constraints),
            _entries(self.original_product_restrictions),
        )
        all_entries = entries + product
        disposition = (
            "no_constraints"
            if not all_entries
            else ("unresolved" if any(e.rule is None for e in all_entries) else "fully_recognized")
        )
        obligations = OBLIGATIONS if any(e.rule is not None for e in all_entries) else ()
        if (self.entries, self.product_entries, self.disposition, self.obligations) != (
            entries,
            product,
            disposition,
            obligations,
        ):
            raise ValueError("complete ordered constraint interpretation required")
        return self

    def assert_inputs(self, inputs: "PlanInputRevision") -> None:
        if type(self).model_validate(self) != interpret_constraints(inputs):
            raise ValueError("constraint interpretation requires exact original inputs")


def interpret_constraints(inputs: "PlanInputRevision") -> ConstraintInterpretationV1:
    from app.planning_documents.context import PlanInputRevision

    inputs = PlanInputRevision.model_validate(inputs)
    product = inputs.creative.product if inputs.creative else None
    restrictions = product.restrictions if product else ()
    entries, product_entries = _entries(inputs.constraints), _entries(restrictions)
    combined = entries + product_entries
    return ConstraintInterpretationV1(
        input_digest=inputs.digest(),
        original_constraints=inputs.constraints,
        entries=entries,
        original_product_restrictions=restrictions,
        product_entries=product_entries,
        disposition="no_constraints"
        if not combined
        else ("unresolved" if any(e.rule is None for e in combined) else "fully_recognized"),
        obligations=OBLIGATIONS if any(e.rule is not None for e in combined) else (),
    )
