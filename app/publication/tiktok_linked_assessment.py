"""Pure discovery consistency and necessary-fact assessment, never write eligibility."""

from typing import Literal

from pydantic import Field, ValidationError, field_validator

from app.collectors.tiktok_discovery_contracts import (
    Frozen,
    TikTokIdentityObservationV1,
    TikTokIdentityPageV1,
    TikTokPixelEventV1,
    TikTokPixelObservationV1,
    TikTokPixelPageV1,
)
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import ExecutionAccount
from app.publication.provider_contracts import Digest

Reason = Literal[
    "publication_contract_not_assessed",
    "pixel_scalar_shape_unverified",
    "page_coverage_only",
    "observation_freshness_not_assessed",
    "custom_identity_phaseout",
    "identity_route_unsupported",
    "identity_status_unknown",
    "identity_unavailable",
    "push_permission_unknown",
    "push_permission_denied",
    "gpppa_status_unknown",
    "gpppa_disallowed",
    "identity_bc_binding_missing",
    "ads_only_mode_unknown",
    "pixel_ownership_unknown",
    "pixel_unbound",
    "pixel_events_unobserved",
    "event_not_selected",
    "event_deprecated",
    "event_deprecation_unknown",
    "event_not_optimizable",
    "optimization_event_unknown",
    "optimization_event_outside_current_profile",
]


class TikTokLinkedAssessmentInputError(ValueError):
    """No raw payload, identifiers or provider errors in the public error."""


class TikTokAssessmentAccountV1(Frozen):
    account_id: int = Field(gt=0)
    connection_id: int = Field(gt=0)
    platform: Literal["google_ads", "meta_ads", "tiktok_ads"]


class TikTokAssessmentScopeV1(Frozen):
    """Immutable exact-shape projection, never a database ownership assertion."""

    workspace_id: int = Field(gt=0)
    account: TikTokAssessmentAccountV1
    external_advertiser_id: str = Field(min_length=1, max_length=128)
    connection_version: str = Field(min_length=1, max_length=100)


class TikTokLinkedAssessmentRequestV1(Frozen):
    schema_version: Literal["inlet.tiktok-linked-assessment-request.v1"] = (
        "inlet.tiktok-linked-assessment-request.v1"
    )
    scope: TikTokAssessmentScopeV1
    identity_page_digest: Digest
    pixel_page_digest: Digest
    identity_id: str = Field(min_length=1, max_length=128)
    pixel_index: int = Field(ge=0, lt=20)
    event_index: int | None = Field(default=None, ge=0, lt=1000)

    @field_validator("scope", mode="before")
    @classmethod
    def snapshot_scope(cls, value: object) -> object:
        if isinstance(value, ExecutionAccount):
            return value.model_dump()
        return value


class TikTokLinkedAssessmentV1(Frozen):
    schema_version: Literal["inlet.tiktok-linked-assessment.v1"] = (
        "inlet.tiktok-linked-assessment.v1"
    )
    request: TikTokLinkedAssessmentRequestV1
    identity: TikTokIdentityObservationV1
    pixel: TikTokPixelObservationV1
    event: TikTokPixelEventV1 | None
    blockers: tuple[Reason, ...]
    publication_eligibility: Literal["not_assessed"] = "not_assessed"
    spending_authority: Literal["none"] = "none"
    tracking_readiness: Literal["unknown"] = "unknown"
    scalar_shape_qualification: Literal["unverified"] = "unverified"
    collection_completeness: Literal["page_only"] = "page_only"
    freshness_assessment: Literal["not_assessed"] = "not_assessed"
    ownership_assessment: Literal["scope_consistency_only"] = "scope_consistency_only"


def identity_page_digest(page: TikTokIdentityPageV1) -> str:
    return fingerprint("inlet.tiktok-identity-page-evidence.v1", page.model_dump(mode="json"))


def pixel_page_digest(page: TikTokPixelPageV1) -> str:
    return fingerprint("inlet.tiktok-pixel-page-evidence.v1", page.model_dump(mode="json"))


def assess_linked_identity(
    request: TikTokLinkedAssessmentRequestV1,
    identity_page: TikTokIdentityPageV1,
    pixel_page: TikTokPixelPageV1,
) -> TikTokLinkedAssessmentV1:
    """Supplied scope consistency is not database ownership or freshness proof."""
    try:
        return _assess(
            TikTokLinkedAssessmentRequestV1.model_validate(request.model_dump()),
            TikTokIdentityPageV1.model_validate(identity_page.model_dump()),
            TikTokPixelPageV1.model_validate(pixel_page.model_dump()),
        )
    except (ValidationError, ValueError, IndexError, TypeError, AttributeError):
        raise TikTokLinkedAssessmentInputError("tiktok_linked_assessment_input_invalid") from None


def _assess(
    request: TikTokLinkedAssessmentRequestV1,
    identities: TikTokIdentityPageV1,
    pixels: TikTokPixelPageV1,
) -> TikTokLinkedAssessmentV1:
    if (
        request.scope.account.platform != "tiktok_ads"
        or identities.request.advertiser_id != request.scope.external_advertiser_id
        or pixels.request.advertiser_id != request.scope.external_advertiser_id
        or identity_page_digest(identities) != request.identity_page_digest
        or pixel_page_digest(pixels) != request.pixel_page_digest
    ):
        raise ValueError("scope")
    matched = [v for v in identities.identities if v.identity_id == request.identity_id]
    if len(matched) != 1:
        raise ValueError("identity")
    identity = matched[0]
    if identity.identity_type.value != identities.request.identity_type:
        raise ValueError("type")
    pixel = pixels.pixels[request.pixel_index]
    events = pixel.events.value or ()
    event = events[request.event_index] if request.event_index is not None else None
    reasons: list[Reason] = [
        "publication_contract_not_assessed",
        "pixel_scalar_shape_unverified",
        "page_coverage_only",
        "observation_freshness_not_assessed",
    ]
    kind = identities.request.identity_type
    if kind == "CUSTOMIZED_USER":
        reasons.append("custom_identity_phaseout")
    elif kind == "AUTH_CODE":
        reasons.append("identity_route_unsupported")
    else:
        status = identity.available_status
        if status.applicability != "applicable" or status.recognition != "recognized":
            reasons.append("identity_status_unknown")
        elif status.value != "AVAILABLE":
            reasons.append("identity_unavailable")
        push = identity.can_push_video
        if push.applicability != "applicable" or push.presence != "present":
            reasons.append("push_permission_unknown")
        elif push.value is not True:
            reasons.append("push_permission_denied")
        gpppa = identity.is_gpppa
        if gpppa.applicability != "applicable" or gpppa.presence != "present":
            reasons.append("gpppa_status_unknown")
        elif gpppa.value is True:
            reasons.append("gpppa_disallowed")
        if kind == "BC_AUTH_TT":
            bc = identity.identity_authorized_bc_id
            if bc.presence != "present":
                reasons.append("identity_bc_binding_missing")
            elif bc.value != identities.request.identity_authorized_bc_id:
                raise ValueError("bc")
            if identity.ads_only_mode.presence != "present" or (
                identity.ads_only_mode.applicability != "applicable"
            ):
                reasons.append("ads_only_mode_unknown")
    ownership = pixel.asset_ownership.value
    if ownership is None:
        reasons.append("pixel_ownership_unknown")
    else:
        relation, owned, bc = (
            ownership.asset_relation_status,
            ownership.ownership_status,
            ownership.owner_bc_id,
        )
        if relation.value == "UNBOUND":
            reasons.append("pixel_unbound")
        consistent = (
            (relation.presence == "null" and owned.value is True and bc.presence == "null")
            or (
                relation.value == "TRANSFERRED" and owned.value is True and bc.presence == "present"
            )
            or (
                relation.value in {"SHARED", "UNBOUND"}
                and owned.value is False
                and bc.presence == "null"
            )
        )
        if not consistent:
            reasons.append("pixel_ownership_unknown")
    if not events:
        reasons.append("pixel_events_unobserved")
    if event is None:
        reasons.append("event_not_selected")
    else:
        if event.deprecated.presence != "present":
            reasons.append("event_deprecation_unknown")
        elif event.deprecated.value:
            reasons.append("event_deprecated")
        # The parser deliberately leaves optimization enum recognition unevaluated.
        # Exact SHOPPING is only the current bounded profile's necessary event fact.
        optimization = event.optimization_event
        if event.event_type.value == "PAGE_VIEW" or optimization.presence == "null":
            reasons.append("event_not_optimizable")
        elif optimization.presence != "present" or optimization.recognition == "unrecognized":
            reasons.append("optimization_event_unknown")
        elif optimization.value != "SHOPPING":
            reasons.append("optimization_event_outside_current_profile")
    return TikTokLinkedAssessmentV1(
        request=request,
        identity=identity,
        pixel=pixel,
        event=event,
        blockers=tuple(dict.fromkeys(reasons)),
    )
