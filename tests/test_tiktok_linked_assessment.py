"""Table-shaped examples through actual parsers, never live eligibility fixtures."""

from typing import Any

import pytest
from app.collectors.tiktok_discovery_parser import parse_identity_page, parse_pixel_page
from app.publication.tiktok_linked_assessment import (
    TikTokLinkedAssessmentInputError,
    TikTokLinkedAssessmentRequestV1,
    assess_linked_identity,
    identity_page_digest,
    pixel_page_digest,
)

from tests.test_tiktok_discovery_parser import envelope, identity_request, pixel_request


def assess(
    kind: str = "TT_USER",
    identity_changes: dict[str, Any] | None = None,
    pixel_changes: dict[str, Any] | None = None,
    event_changes: dict[str, Any] | None = None,
) -> Any:
    identity = dict(
        identity_id="identity",
        identity_type=kind,
        available_status="AVAILABLE",
        can_push_video=True,
        is_gpppa=False,
    )
    kwargs = {}
    if kind == "BC_AUTH_TT":
        kwargs["identity_authorized_bc_id"] = "bc"
        identity.update(identity_authorized_bc_id="bc", ads_only_mode=True)
    identity.update(identity_changes or {})
    event = dict(event_id=123, optimization_event="SHOPPING", deprecated=False)
    event.update(event_changes or {})
    pixel = dict(
        pixel_id="00123",
        asset_ownership=dict(asset_relation_status=None, ownership_status=True, owner_bc_id=None),
        events=[event],
    )
    pixel.update(pixel_changes or {})
    identities = parse_identity_page(
        identity_request(identity_type=kind, **kwargs), envelope("identity_list", [identity], 20)
    )
    pixels = parse_pixel_page(pixel_request(), envelope("pixels", [pixel]))
    request = TikTokLinkedAssessmentRequestV1.model_validate(
        dict(
            scope=dict(
                workspace_id=1,
                account=dict(platform="tiktok_ads", account_id=1, connection_id=1),
                external_advertiser_id="synthetic-advertiser",
                connection_version="generation1",
            ),
            identity_page_digest=identity_page_digest(identities),
            pixel_page_digest=pixel_page_digest(pixels),
            identity_id="identity",
            pixel_index=0,
            event_index=0 if pixel["events"] else None,
        )
    )
    return request, identities, pixels


@pytest.mark.parametrize("kind", ["TT_USER", "BC_AUTH_TT"])
def test_complete_facts_never_qualify(kind: str) -> None:
    args = assess(kind)
    result = assess_linked_identity(*args)
    assert len(result.blockers) == 4
    assert result.publication_eligibility == "not_assessed"
    assert result.spending_authority == "none"
    assert result.ownership_assessment == "scope_consistency_only"
    assert result.pixel.pixel_id.value == "00123"
    assert result.event and type(result.event.event_id.value) is int
    assert result.event.optimization_event.recognition == "not_evaluated"
    assert result == assess_linked_identity(*args)


@pytest.mark.parametrize(
    "kind,reason",
    [("CUSTOMIZED_USER", "custom_identity_phaseout"), ("AUTH_CODE", "identity_route_unsupported")],
)
def test_other_routes_do_not_require_inapplicable_status(kind: str, reason: str) -> None:
    result = assess_linked_identity(*assess(kind, {"available_status": None}))
    assert reason in result.blockers
    assert "identity_status_unknown" not in result.blockers


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"available_status": None}, "identity_status_unknown"),
        ({"available_status": "FUTURE"}, "identity_status_unknown"),
        ({"available_status": "SCOPE_UNAVAILABLE"}, "identity_unavailable"),
        ({"can_push_video": None}, "push_permission_unknown"),
        ({"can_push_video": False}, "push_permission_denied"),
        ({"is_gpppa": None}, "gpppa_status_unknown"),
        ({"is_gpppa": True}, "gpppa_disallowed"),
    ],
)
def test_identity_negative_facts(changes: dict[str, Any], reason: str) -> None:
    assert reason in assess_linked_identity(*assess(identity_changes=changes)).blockers


def test_bc_absent_facts() -> None:
    result = assess_linked_identity(
        *assess("BC_AUTH_TT", dict(identity_authorized_bc_id=None, ads_only_mode=None))
    )
    assert "identity_bc_binding_missing" in result.blockers
    assert "ads_only_mode_unknown" in result.blockers


@pytest.mark.parametrize(
    "relation,owned,bc,blocked",
    [
        ("UNBOUND", False, None, True),
        ("SHARED", False, None, False),
        ("TRANSFERRED", True, "other-owner-bc", False),
        (None, True, None, False),
    ],
)
def test_pixel_ownership_not_identity_ownership(
    relation: Any, owned: bool, bc: Any, blocked: bool
) -> None:
    result = assess_linked_identity(
        *assess(
            pixel_changes={
                "asset_ownership": dict(
                    asset_relation_status=relation, ownership_status=owned, owner_bc_id=bc
                )
            }
        )
    )
    assert ("pixel_unbound" in result.blockers) is blocked
    assert "pixel_ownership_unknown" not in result.blockers


@pytest.mark.parametrize(
    "event,reason",
    [
        ({"deprecated": True}, "event_deprecated"),
        ({"deprecated": None}, "event_deprecation_unknown"),
        ({"event_type": "PAGE_VIEW", "optimization_event": None}, "event_not_optimizable"),
        ({"optimization_event": "FUTURE"}, "optimization_event_outside_current_profile"),
    ],
)
def test_event_facts(event: dict[str, Any], reason: str) -> None:
    assert reason in assess_linked_identity(*assess(event_changes=event)).blockers


def test_empty_events_are_unobserved() -> None:
    result = assess_linked_identity(*assess(pixel_changes={"events": []}))
    assert "pixel_events_unobserved" in result.blockers
    assert "event_not_selected" in result.blockers
    assert result.tracking_readiness == "unknown"


@pytest.mark.parametrize("damage", ["digest", "scope", "index", "duplicate", "typed", "bc"])
def test_reject_rehashed_and_model_copy_input_damage(damage: str) -> None:
    request, identities, pixels = assess("BC_AUTH_TT")
    if damage == "digest":
        request = request.model_copy(update={"pixel_page_digest": "0" * 64})
    elif damage == "scope":
        request = request.model_copy(
            update={"scope": request.scope.model_copy(update={"external_advertiser_id": "foreign"})}
        )
    elif damage == "index":
        request = request.model_copy(update={"event_index": 50})
    else:
        row = identities.identities[0]
        if damage == "duplicate":
            identities = identities.model_copy(update={"identities": (row, row)})
        elif damage == "typed":
            identities = identities.model_copy(
                update={
                    "identities": (
                        row.model_copy(
                            update={
                                "can_push_video": row.can_push_video.model_copy(
                                    update={"value": "true"}
                                )
                            }
                        ),
                    )
                }
            )
        else:
            identities = identities.model_copy(
                update={
                    "identities": (
                        row.model_copy(
                            update={
                                "identity_authorized_bc_id": (
                                    row.identity_authorized_bc_id
                                ).model_copy(update={"value": "different"})
                            }
                        ),
                    )
                }
            )
        request = request.model_copy(
            update={"identity_page_digest": identity_page_digest(identities)}
        )
    with pytest.raises(
        TikTokLinkedAssessmentInputError, match="^tiktok_linked_assessment_input_invalid$"
    ):
        assess_linked_identity(request, identities, pixels)


def test_nested_scope_is_frozen_and_does_not_alias_execution_account() -> None:
    from app.publication.execution_contracts import ExecutionAccount
    from pydantic import ValidationError

    request, identities, pixels = assess()
    original = ExecutionAccount.model_validate(request.scope.model_dump())
    copied = TikTokLinkedAssessmentRequestV1.model_validate(
        {**request.model_dump(), "scope": original}
    )
    result = assess_linked_identity(copied, identities, pixels)
    original.account.account_id = 999
    original.connection_version = "changed"
    assert result.request.scope.account.account_id == 1
    assert result.request.scope.connection_version == "generation1"
    with pytest.raises(ValidationError, match="frozen"):
        result.request.scope.account.account_id = 2  # type: ignore[misc]
    with pytest.raises(ValidationError, match="frozen"):
        result.request.scope.connection_version = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        TikTokLinkedAssessmentRequestV1.model_validate(
            {**request.model_dump(), "event_index": 1000}
        )
