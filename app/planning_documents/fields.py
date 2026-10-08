"""Bounded declarative suggestions and comparison results, not provider payloads."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.planning_documents.common import Frozen, Key, Text


class StatusValue(Frozen):
    field: Literal["delivery_status"]
    value: Literal["enabled", "paused"]


class LandingPageValue(Frozen):
    field: Literal["landing_page"]
    value: Annotated[str, Field(strict=True, pattern=r"^https://[^\s]+$", max_length=2048)]


class TargetingValue(Frozen):
    field: Literal["country_targets"]
    value: tuple[Annotated[str, Field(strict=True, pattern=r"^[A-Z]{2}$")], ...] = Field(
        min_length=1, max_length=50
    )


SupportedValue = Annotated[
    StatusValue | LandingPageValue | TargetingValue, Field(discriminator="field")
]


class ProposedField(Frozen):
    key: Key
    availability: Literal["supported"]
    current: SupportedValue
    proposed: SupportedValue
    evidence_key: Key
    verification_criterion: Text

    @model_validator(mode="after")
    def same_field(self) -> "ProposedField":
        if self.current.field != self.proposed.field:
            raise ValueError("current/proposed field mismatch")
        return self


class UnavailableField(Frozen):
    key: Key
    availability: Literal["unavailable"]
    field: Literal["delivery_status", "landing_page", "country_targets", "bidding", "native_budget"]
    reason: Text
    proposed: None = None


FieldProposal = Annotated[ProposedField | UnavailableField, Field(discriminator="availability")]
