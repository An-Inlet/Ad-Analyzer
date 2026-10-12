"""Only the qualified Meta count graph gains planning projection support."""

import pytest
from app.campaign_performance.selected_contracts import (
    CustomerEventSelectionV1,
    SelectedCaptureRequestV1,
    capture_request_digest,
    selection_digest,
)
from app.planning_documents.selected_plan_bundle import supported
from app.planning_documents.selected_plan_evidence import SelectedPlanCaptureV1

from tests.test_capture_settings_contract import social
from tests.test_meta_selected_count import request


@pytest.mark.parametrize(
    "profile",
    ["count", "meta.website-purchase.campaign-day.v1", "tiktok.website-payment.campaign-day.v1"],
)
def test_only_qualified_count_profile_is_projectable(profile: str) -> None:
    req = request()
    if profile != "count":
        setting = social(profile)
        body = req.model_dump(mode="json")
        choice = body["selection"]
        if profile.startswith("tiktok"):
            body["aggregate"]["scope"].update(platform="tiktok_ads", source_connection_ref="a" * 32)
            choice.update(
                scope=body["aggregate"]["scope"],
                api_version="v1.3",
                metric_family="event_count",
                event_namespace="tiktok_event",
                native_event_id="complete_payment",
            )
        choice["query_profile_digest"] = setting.query_digest()
        body.update(
            settings=setting.model_dump(mode="json"),
            attribution=setting.effective.model_dump(mode="json"),
            producer_contract=setting.producer(),
            query_profile_digest=setting.query_digest(),
            selection_digest=selection_digest(CustomerEventSelectionV1.model_validate(choice)),
        )
        req = SelectedCaptureRequestV1.model_validate(body)
    scope = req.aggregate.scope
    graph = SelectedPlanCaptureV1.model_validate(
        dict(
            source_fence=dict(
                account=dict(
                    workspace_id=scope.workspace_id,
                    connection_id=scope.connection_id,
                    account_id=scope.account_id,
                    platform=scope.platform,
                    connection_version=str(scope.generation),
                ),
                source_binding_digest="b" * 64,
                source_revision=str(scope.generation),
                privacy_revision=scope.privacy_revision,
            ),
            capture=dict(
                schema_version="inlet.selected-capture.v2",
                request=req,
                request_digest=capture_request_digest(req),
                completed_at=req.started_at,
                capability="supported" if profile == "count" else "unknown",
                pagination_complete=True,
                page_count=1,
                facts=[],
            ),
            campaigns=[],
        )
    )
    assert supported(graph) is (profile == "count")
