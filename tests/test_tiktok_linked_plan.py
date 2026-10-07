"""Independent canonical Push graph and original request binding."""

from datetime import timedelta

import pytest
from app.publication.social_compiler import compile_social
from app.publication.social_contracts import SocialProviderReceipt
from app.publication.tiktok_linked_plan import (
    LINKED_OUTPUTS,
    LinkedPushBoundRequestV1,
    LinkedPushPlanV1,
    LinkedPushPublicationReviewV1,
    compile_linked_push,
    creative_for,
    materialize_linked_push,
)
from pydantic import ValidationError

from tests.test_commerce_measurement import NOW
from tests.test_social_publication_http import tiktok_reviewed


def linked_review() -> LinkedPushPublicationReviewV1:
    old = tiktok_reviewed()
    fields = old.configuration.model_dump(mode="json")
    del fields["identity_type"], fields["identity_id"]
    fields.update(
        kind="tiktok_linked_push_v13",
        identity=dict(identity_type="TT_USER", identity_id="linked"),
        rights_review_digest="a" * 64,
        identity_observation_digest="b" * 64,
        advertiser_observation_digest="c" * 64,
        commercial_music_rights_reviewed=True,
        linked_post_creation_reviewed=True,
        dark_post_status="ON",
        creative_authorized=False,
    )
    return LinkedPushPublicationReviewV1.model_validate(
        dict(
            source=old.source,
            source_digest=old.source_digest,
            scope=old.scope,
            configuration=fields,
            configuration_review=dict(
                review_id="a" * 32, review_digest="b" * 64, approval_digest="c" * 64
            ),
            qualification_blockers=["contract_scenario_not_live_qualification"],
        )
    )


def test_new_plan_preserves_old_hash_and_exact_linked_media_and_copy() -> None:
    old = tiktok_reviewed()
    old_hash = compile_social(old).digest()
    review = linked_review()
    plan = compile_linked_push(review)
    assert [s.step_id for s in plan.steps] == ["video", "cover", "campaign", "adgroup", "ad"]
    assert plan.compiler_id == "tiktok_linked_push_v13_v1"
    assert not plan.publication_eligible
    assert "CUSTOMIZED_USER" not in plan.model_dump_json()
    assert compile_social(old).digest() == old_hash
    assert LinkedPushPlanV1.model_validate_json(plan.model_dump_json()).digest() == plan.digest()
    creative = creative_for(review, "original-video", "original-cover")
    assert creative.video_id == "original-video" and creative.image_ids == ("original-cover",)
    assert creative.dark_post_status == "ON" and creative.operation_status == "DISABLE"
    bad = plan.model_dump(mode="json")
    bad["steps"][3]["operation"]["name"] = "Unreviewed name"
    with pytest.raises(ValidationError):
        LinkedPushPlanV1.model_validate(bad)
    bad_review = review.model_dump(mode="json")
    bad_review["configuration"]["cover"]["width"] += 1
    with pytest.raises(ValidationError):
        LinkedPushPublicationReviewV1.model_validate(bad_review)


def test_linked_request_cannot_substitute_review_or_foreign_resource() -> None:
    review = linked_review()
    plan = compile_linked_push(review)
    request = LinkedPushBoundRequestV1(
        plan_id="a" * 32,
        plan_digest=plan.digest(),
        review_digest=review.digest(),
        scope=review.scope,
        step=plan.steps[-1],
        review=review,
        resources={
            "adgroup": f"tiktok/{review.scope.external_advertiser_id}/adgroups/12",
            "video": f"tiktok/{review.scope.external_advertiser_id}/videos/library",
            "cover": f"tiktok/{review.scope.external_advertiser_id}/images/cover",
        },
        fence="f" * 32,
        dispatched_at=NOW,
    )
    assert (
        LinkedPushBoundRequestV1.model_validate_json(request.model_dump_json()).digest()
        == request.digest()
    )
    for fields in (
        {"plan_digest": "0" * 64},
        {"resources": {**request.resources, "video": "tiktok/999/videos/foreign"}},
    ):
        with pytest.raises(ValidationError):
            LinkedPushBoundRequestV1.model_validate({**request.model_dump(), **fields})


def test_materializer_requires_every_original_verified_dependency() -> None:
    plan = compile_linked_push(linked_review())
    requests: dict[str, LinkedPushBoundRequestV1] = {}
    receipts: dict[str, SocialProviderReceipt] = {}
    for index, step in enumerate(plan.steps):
        request = materialize_linked_push(
            plan, "a" * 32, step.step_id, receipts, requests, "f" * 32, NOW
        )
        requests[step.step_id] = request
        receipts[step.step_id] = SocialProviderReceipt(
            scope=plan.review.scope,
            plan_id=request.plan_id,
            plan_digest=plan.digest(),
            step_id=step.step_id,
            fence=request.fence,
            request_digest=request.digest(),
            outcome="verified_effect",
            resource_kind=LINKED_OUTPUTS[step.operation.kind],
            resource_name=(
                f"tiktok/{plan.review.scope.external_advertiser_id}/"
                f"{LINKED_OUTPUTS[step.operation.kind]}/{index + 100}"
            ),
            readback_digest="d" * 64,
            evidence="exact_readback",
            observed_at=NOW,
        )
    assert requests["ad"].resources == {
        name: receipts[name].resource_name for name in ("video", "cover", "adgroup")
    }
    # Campaign has no direct ad resource reference, but its receipt is still mandatory.
    for missing in ("video", "cover", "campaign", "adgroup"):
        with pytest.raises(ValueError, match="verified linked dependency"):
            materialize_linked_push(
                plan,
                "a" * 32,
                "ad",
                {key: value for key, value in receipts.items() if key != missing},
                requests,
                "f" * 32,
                NOW,
            )
    original = receipts["campaign"]
    for changed in (
        {"request_digest": "0" * 64},
        {"fence": "0" * 32},
        {"plan_id": "0" * 32},
        {"observed_at": NOW + timedelta(seconds=1)},
        {
            "outcome": "unknown",
            "resource_name": None,
            "readback_digest": None,
            "evidence": "unresolved",
        },
    ):
        altered = SocialProviderReceipt.model_validate({**original.model_dump(), **changed})
        with pytest.raises(ValueError, match="stale or foreign linked dependency"):
            materialize_linked_push(
                plan,
                "a" * 32,
                "ad",
                {**receipts, "campaign": altered},
                requests,
                "f" * 32,
                NOW,
            )
