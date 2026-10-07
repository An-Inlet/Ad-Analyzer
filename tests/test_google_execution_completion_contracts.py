from copy import deepcopy
from typing import Any

import pytest
from app.executors.google_publication import serialize
from app.publication.contracts import fingerprint
from app.publication.google_compiler import compile_google, materialize_google
from app.publication.google_execution_completion_contracts import (
    GoogleCapturedCreationResponse,
    GoogleExecutionCompletionV2,
    OriginalOperationCompletionView,
    capture_success,
    parse_completion,
)
from app.publication.provider_contracts import (
    BoundProviderRequest,
    ProviderReceipt,
    ProviderResponse,
)

from tests.test_google_total_publication import total_review
from tests.test_provider_publication_contracts import NOW, review


def requests(total: bool = False) -> list[tuple[BoundProviderRequest, dict[str, Any]]]:
    plan = compile_google(total_review() if total else review())
    prior: dict[str, BoundProviderRequest] = {}
    receipts: dict[str, ProviderReceipt] = {}
    result = []
    for index, step in enumerate(plan.steps):
        request = materialize_google(
            plan, "c" * 32, step.step_id, receipts, prior, f"{index:032x}", NOW
        )
        collection, _, op = serialize(request)
        suffix = str(index + 1)
        if collection in {"campaignCriteria", "adGroupCriteria", "adGroupAds"}:
            parent = op["create"].get("campaign", op["create"].get("adGroup"))
            suffix = parent.rsplit("/", 1)[1] + "~" + suffix
        resource = op.get("update", {}).get(
            "resourceName", f"customers/1234567890/{collection}/{suffix}"
        )
        wire = {"results": [{"resourceName": resource}]}
        result.append((request, wire))
        prior[step.step_id] = request
        receipts[step.step_id] = ProviderReceipt(
            scope=request.scope,
            plan_id=request.plan_id,
            plan_digest=request.plan_digest,
            step_id=step.step_id,
            fence=request.fence,
            request_digest=request.digest(),
            outcome="verified_effect",
            resource_name=resource,
            readback_digest="a" * 64,
            evidence="exact_readback",
            observed_at=NOW,
        )
    return result


@pytest.mark.parametrize("total", [False, True])
def test_all_seven_services_capture_exact_lineage_and_preserve_response_bytes(total: bool) -> None:
    seen = set()
    for request, wire in requests(total):
        capture = capture_success(request, wire)
        seen.add(capture.endpoint)
        response = GoogleCapturedCreationResponse(
            request_digest=request.digest(),
            outcome="acknowledged",
            resource_name=capture.resource_name,
            capture=capture,
        )
        old = ProviderResponse(
            request_digest=request.digest(),
            outcome="acknowledged",
            resource_name=capture.resource_name,
        )
        assert response.model_dump_json() == old.model_dump_json()
        document = GoogleExecutionCompletionV2(
            capture=capture,
            environment="contract_test",
            attempt_id="d" * 32,
            run_id=request.plan_id,
            step_id=request.step.step_id,
            normalized_response_digest=fingerprint(
                "inlet.provider-response.v1", old.model_dump(mode="json")
            ),
            recorded_at=NOW,
        )
        document.bind(request, NOW)
        assert parse_completion(document.model_dump(mode="json")) == document
        assert capture.partial_failure == (
            "unsupported" if capture.endpoint.startswith("conversionGoal") else "false"
        )
    assert len(seen) == 7


@pytest.mark.parametrize(
    "mode", ["extra", "partial", "empty", "duplicate", "foreign", "parent", "update"]
)
def test_ambiguous_or_wrong_original_result_never_captures(mode: str) -> None:
    cases = requests()
    request, wire = next(
        (r, w)
        for r, w in cases
        if serialize(r)[0]
        == ("conversionGoalCampaignConfigs" if mode == "update" else "campaignCriteria")
    )
    wire = deepcopy(wire)
    if mode == "extra":
        wire["operation"] = "async"
    elif mode == "partial":
        wire["partialFailureError"] = {}
    elif mode == "empty":
        wire["results"] = []
    elif mode == "duplicate":
        wire["results"] *= 2
    elif mode == "foreign":
        wire["results"][0]["resourceName"] = wire["results"][0]["resourceName"].replace(
            "1234567890", "9999999999"
        )
    elif mode == "parent":
        wire["results"][0]["resourceName"] = "customers/1234567890/campaignCriteria/999~9"
    else:
        wire["results"][0]["resourceName"] = (
            "customers/1234567890/conversionGoalCampaignConfigs/999"
        )
    with pytest.raises(ValueError):
        capture_success(request, wire)


def test_projection_never_implies_financial_finality_or_partial_proof() -> None:
    assert OriginalOperationCompletionView().financial_finality == "unavailable"
    with pytest.raises(ValueError):
        OriginalOperationCompletionView(status="completed")
    with pytest.raises(ValueError):
        OriginalOperationCompletionView(commitment="a" * 64)
