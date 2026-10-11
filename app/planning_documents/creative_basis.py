"""Standalone declared product and owned-image contracts; parsing grants no authority."""

import re
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import AwareDatetime, Field, field_validator, model_validator

from app.campaign_review.contracts import MAX_IMAGE_BYTES, MAX_LIBRARY_BYTES, MAX_PIXELS
from app.planning_documents.common import (
    Amount,
    Currency,
    Digest,
    Id,
    NoAuthority,
    Positive,
    Text,
    Title,
    unique,
)


def _ordered(value: Any) -> Any:
    if type(value) not in (list, tuple):
        raise ValueError("explicit ordered collection required")
    return value


def _instant(value: Any) -> Any:
    if type(value) is not datetime and not (
        type(value) is str and re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T", value)
    ):
        raise ValueError("aware ISO instant required")
    return value


class CustomerListPriceV1(NoAuthority):
    micros: Amount
    currency: Currency


class CustomerProductV1(NoAuthority):
    schema_version: Literal["inlet.customer-product.v1"] = "inlet.customer-product.v1"
    name: Title
    list_price: CustomerListPriceV1 | None = None
    customer_asserted_facts: tuple[Text, ...] = Field(default=(), max_length=20)
    restrictions: tuple[Text, ...] = Field(default=(), max_length=20)
    provenance: Literal["customer_supplied"] = "customer_supplied"
    claim_review: Literal["required"] = "required"

    _order = field_validator("customer_asserted_facts", "restrictions", mode="before")(_ordered)


class PlanningMediaSelectionV1(NoAuthority):
    schema_version: Literal["inlet.planning-media-selection.v1"] = (
        "inlet.planning-media-selection.v1"
    )
    media_id: Id
    expected_sha256: Digest


class CreativeInputV1(NoAuthority):
    schema_version: Literal["inlet.creative-input.v1"] = "inlet.creative-input.v1"
    product: CustomerProductV1 | None = None
    media_selections: tuple[PlanningMediaSelectionV1, ...] = Field(default=(), max_length=30)

    _order = field_validator("media_selections", mode="before")(_ordered)

    @model_validator(mode="after")
    def unique_media(self) -> "CreativeInputV1":
        unique(tuple(item.media_id for item in self.media_selections), "selected media ID")
        return self


class OwnedPlanningImageV1(NoAuthority):
    schema_version: Literal["inlet.owned-planning-image.v1"] = "inlet.owned-planning-image.v1"
    workspace_id: Positive
    media_id: Id
    sha256: Digest
    size: int = Field(strict=True, ge=1, le=MAX_IMAGE_BYTES)
    mime: Literal["image/png", "image/jpeg"]
    width: Positive
    height: Positive
    created_at: AwareDatetime
    observed_at: AwareDatetime
    privacy_revision: int = Field(strict=True, ge=0)
    visual_assessment: Literal["not_assessed"] = "not_assessed"

    _instants = field_validator("created_at", "observed_at", mode="before")(_instant)

    @field_validator("created_at", "observed_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def bounds(self) -> "OwnedPlanningImageV1":
        if self.width * self.height > MAX_PIXELS:
            raise ValueError("image pixel bound exceeded")
        if self.created_at > self.observed_at:
            raise ValueError("image observation precedes creation")
        return self


class CreativeBasisV1(NoAuthority):
    schema_version: Literal["inlet.creative-basis.v1"] = "inlet.creative-basis.v1"
    workspace_id: Positive
    goal_currency: Currency
    privacy_revision: int = Field(strict=True, ge=0)
    requested: CreativeInputV1
    images: tuple[OwnedPlanningImageV1, ...] = Field(max_length=30)

    _order = field_validator("images", mode="before")(_ordered)

    @model_validator(mode="after")
    def exact(self) -> "CreativeBasisV1":
        if tuple(
            (item.media_id, item.expected_sha256) for item in self.requested.media_selections
        ) != tuple((image.media_id, image.sha256) for image in self.images):
            raise ValueError("exact ordered selected image witnesses required")
        if any(
            image.workspace_id != self.workspace_id
            or image.privacy_revision != self.privacy_revision
            for image in self.images
        ):
            raise ValueError("foreign image workspace or privacy revision")
        product = self.requested.product
        if (
            product is not None
            and product.list_price is not None
            and product.list_price.currency != self.goal_currency
        ):
            raise ValueError("product price must use goal currency")
        if sum(image.size for image in self.images) > MAX_LIBRARY_BYTES:
            raise ValueError("image library byte bound exceeded")
        return self
