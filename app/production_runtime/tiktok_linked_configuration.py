"""Pinned explicit linked Push profiles; existing v1 bundle bytes stay unchanged."""

import json
from dataclasses import dataclass
from typing import Literal

from pydantic import Field, model_validator

from app.initial_planning.contracts import Frozen
from app.planning_reporting.configuration import _unique_object
from app.publication.contracts import fingerprint
from app.publication.social_catalog import TikTokConfigurationProfile
from app.publication.social_review_contracts import SocialRequirements


class LinkedBundleDocument(Frozen):
    schema_version: Literal["inlet.tiktok-linked-push-configuration-bundle.v1"] = (
        "inlet.tiktok-linked-push-configuration-bundle.v1"
    )
    identity_type: Literal["TT_USER"]
    dark_post_status: Literal["ON"]
    profiles: tuple[TikTokConfigurationProfile, ...] = Field(min_length=1, max_length=10)
    requirements: tuple[SocialRequirements, ...] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def exact(self) -> "LinkedBundleDocument":
        profiles = [value.digest() for value in self.profiles]
        rules = [value.profile_digest for value in self.requirements]
        if (
            len(set(profiles)) != len(profiles)
            or len(set(rules)) != len(rules)
            or set(profiles) != set(rules)
            or any(p.currency != "USD" or p.currency_exponent != 2 for p in self.profiles)
            or any(not r.wording or not r.wording.strip() for r in self.requirements)
        ):
            raise ValueError("exact linked profile and reviewed wording required")
        return self


@dataclass(frozen=True)
class TikTokLinkedConfigurationBundleV1:
    _canonical: bytes

    def __post_init__(self) -> None:
        document = LinkedBundleDocument.model_validate(
            json.loads(self._canonical, object_pairs_hook=_unique_object)
        )
        object.__setattr__(self, "_canonical", document.model_dump_json().encode())

    @classmethod
    def from_document(cls, value: object) -> "TikTokLinkedConfigurationBundleV1":
        return cls(LinkedBundleDocument.model_validate(value).model_dump_json().encode())

    @property
    def profiles(self) -> tuple[TikTokConfigurationProfile, ...]:
        return LinkedBundleDocument.model_validate_json(self._canonical).profiles

    @property
    def requirements(self) -> tuple[SocialRequirements, ...]:
        return LinkedBundleDocument.model_validate_json(self._canonical).requirements

    def digest(self) -> str:
        document = LinkedBundleDocument.model_validate_json(self._canonical)
        return fingerprint(document.schema_version, document.model_dump(mode="json"))
