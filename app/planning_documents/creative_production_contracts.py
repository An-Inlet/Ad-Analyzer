"""Standalone production proposals, not ready assets or publication authority."""

import json
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.planning_documents.actions import CreativeBrief, ManualAction
from app.planning_documents.common import (
    MAX_ACTIONS,
    MAX_DOCUMENT_BYTES,
    Digest,
    Id,
    Key,
    NoAuthority,
    Text,
    unique,
)
from app.planning_documents.creative_basis import (
    CreativeBasisV1,
    PlanningMediaSelectionV1,
    _ordered,
)


class CreativeShotV1(NoAuthority):
    purpose: Literal["introduction", "demonstration", "cta"]
    capture_instruction: Text
    proposed_caption: Text


class CreativeProductionV1(NoAuthority):
    schema_version: Literal["inlet.creative-production.v1"] = "inlet.creative-production.v1"
    source_images: tuple[PlanningMediaSelectionV1, ...] = Field(max_length=30)
    selected_image_id: Id | None
    source_image_status: Literal["owned_bytes_observed", "not_supplied"]
    deliverable: Literal["image_creative", "video"]
    deliverable_status: Literal["production_required"] = "production_required"
    visual_assessment: Literal["not_assessed"] = "not_assessed"
    basis_evidence_key: Key
    storyboard: tuple[CreativeShotV1, ...] = Field(max_length=3)

    _order = field_validator("source_images", "storyboard", mode="before")(_ordered)

    @model_validator(mode="after")
    def coherent(self) -> "CreativeProductionV1":
        unique(tuple(x.media_id for x in self.source_images), "source image")
        expected_id = self.source_images[0].media_id if self.source_images else None
        expected_status = "owned_bytes_observed" if self.source_images else "not_supplied"
        if (self.selected_image_id, self.source_image_status) != (expected_id, expected_status):
            raise ValueError("exact first selected image and availability required")
        purposes = tuple(x.purpose for x in self.storyboard)
        if purposes != (
            () if self.deliverable == "image_creative" else ("introduction", "demonstration", "cta")
        ):
            raise ValueError("exact deliverable storyboard required")
        return self


class CreativeProposalV1(NoAuthority):
    schema_version: Literal["inlet.creative-proposal.v1"] = "inlet.creative-proposal.v1"
    action: ManualAction
    brief: CreativeBrief
    production: CreativeProductionV1

    @model_validator(mode="after")
    def coherent(self) -> "CreativeProposalV1":
        action, brief, production = self.action, self.brief, self.production
        if (
            action.key != f"creative:account_{action.target.account.account_id}"
            or brief.key != f"brief:account_{action.target.account.account_id}"
            or action.kind != "creative_review"
            or action.priority > MAX_ACTIONS
            or action.native_budget is not None
            or action.proposed_fields
            or brief.action_key != action.key
            or brief.key == action.key
            or brief.target != action.target
            or production.basis_evidence_key not in action.evidence_keys
            or not set(brief.claim_evidence_keys) <= set(action.evidence_keys)
            or getattr(action.target, "kind", None) != "campaign"
            or action.target.account.platform not in {"meta_ads", "tiktok_ads"}
            or production.deliverable
            != ("image_creative" if action.target.account.platform == "meta_ads" else "video")
        ):
            raise ValueError("incoherent creative proposal")
        return self


class CreativeCompositionV1(NoAuthority):
    schema_version: Literal["inlet.creative-composition.v1"] = "inlet.creative-composition.v1"
    basis_digest: Digest
    proposals: tuple[CreativeProposalV1, ...] = Field(max_length=30)
    limitations: tuple[Text, ...] = Field(max_length=100)

    _order = field_validator("proposals", "limitations", mode="before")(_ordered)

    @model_validator(mode="after")
    def coherent(self) -> "CreativeCompositionV1":
        keys = tuple(x for p in self.proposals for x in (p.action.key, p.brief.key))
        unique(keys, "creative proposal key")
        priorities = tuple(p.action.priority for p in self.proposals)
        if priorities and priorities != tuple(
            range(priorities[0], priorities[0] + len(priorities))
        ):
            raise ValueError("contiguous ordered creative priorities required")
        unique(
            tuple(p.action.target.account.account_id for p in self.proposals), "creative account"
        )
        if (
            len(
                json.dumps(
                    self.model_dump(mode="json"),
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode()
            )
            > MAX_DOCUMENT_BYTES
        ):
            raise ValueError("complete creative composition exceeds document byte limit")
        return self

    def assert_basis(self, supplied: CreativeBasisV1) -> None:
        current = type(self).model_validate(self)
        basis = CreativeBasisV1.model_validate(supplied)
        if current.basis_digest != basis.digest() or any(
            p.production.source_images != basis.requested.media_selections
            or p.action.target.account.workspace_id != basis.workspace_id
            for p in current.proposals
        ):
            raise ValueError("creative proposal requires complete exact basis")
