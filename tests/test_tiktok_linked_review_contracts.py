"""Separate exact linked customer declarations; no provider authority from an answer."""

from datetime import timedelta
from typing import Any

import pytest
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import ExecutionAccount
from app.publication.social_customer_producer import catalog_request
from app.publication.social_review_contracts import SocialConfigurationDocument, SocialRequirements
from app.publication.tiktok_linked_contracts import (
    AdvertiserCapabilitiesObservationV1,
    IdentityInfoObservationV1,
)
from app.publication.tiktok_linked_plan import (
    LinkedPushConfigurationV1,
    LinkedPushPublicationReviewV1,
)
from app.publication.tiktok_linked_review_contracts import (
    LinkedPushConfigurationDocumentV1,
    LinkedPushCustomerAnswerV1,
    linked_rights_digest,
)
from pydantic import ValidationError

from tests.test_commerce_measurement import NOW
from tests.test_tiktok_linked_plan import linked_review


def document(
    review: LinkedPushPublicationReviewV1 | None = None,
) -> LinkedPushConfigurationDocumentV1:
    review = review or linked_review()
    account = ExecutionAccount.from_publication(review.scope)
    request = catalog_request(review.source, account)
    owner = dict(
        workspace_id=account.workspace_id,
        account_id=account.account.account_id,
        connection_id=account.account.connection_id,
        external_advertiser_id=account.external_advertiser_id,
        connection_version=account.connection_version,
    )
    absent = dict(presence="absent", value=None)
    identity = IdentityInfoObservationV1.model_validate(
        dict(
            request=dict(owner=owner, identity=review.configuration.identity),
            observed_at=NOW,
            expires_at=NOW + timedelta(minutes=5),
            available_status="AVAILABLE",
            is_gpppa=dict(presence="present", value=False),
            can_push_video=dict(presence="present", value=True),
            can_pull_video=absent,
            ads_only_mode=absent,
        )
    )
    advertiser = AdvertiserCapabilitiesObservationV1.model_validate(
        dict(
            request=dict(owner=owner, fields=("ads_only_mode", "can_use_custom_identity")),
            observed_at=NOW,
            expires_at=NOW + timedelta(minutes=5),
            ads_only_mode=absent,
            can_use_custom_identity=absent,
        )
    )
    requirements = SocialRequirements(
        profile_digest="d" * 64,
        requirements_digest="e" * 64,
        wording_version="linked-v1",
        verified=True,
        dsa_required=False,
        wording="Review music rights and a new ads-only linked post.",
    )
    answer = LinkedPushCustomerAnswerV1(
        reviewed_video_and_cover=True,
        commercial_music_rights_reviewed=True,
        creates_new_linked_post_reviewed=True,
        ads_only_visibility_reviewed=True,
    )
    values = review.configuration.model_dump()
    values.update(
        identity_observation_digest=identity.digest(),
        advertiser_observation_digest=advertiser.digest(),
        rights_review_digest=linked_rights_digest(
            request, requirements, answer, review.configuration
        ),
    )
    configuration = LinkedPushConfigurationV1.model_validate(values)
    return LinkedPushConfigurationDocumentV1(
        identity_label="Reviewed Linked Account",
        request=request,
        environment="contract_test",
        option_id="f" * 64,
        requirements=requirements,
        answer=answer,
        identity_observation=identity,
        advertiser_observation=advertiser,
        configuration=configuration,
        configuration_digest=fingerprint(
            "inlet.tiktok-linked-push-configuration-fields.v1",
            configuration.model_dump(mode="json"),
        ),
    )


def test_exact_linked_document_does_not_parse_as_old_social_approval() -> None:
    saved = document()
    assert LinkedPushConfigurationDocumentV1.model_validate_json(saved.model_dump_json()) == saved
    with pytest.raises(ValidationError):
        SocialConfigurationDocument.model_validate(saved.model_dump())
    changed = saved.model_dump()
    changed["requirements"]["wording"] = "Different declaration"
    with pytest.raises(ValidationError):
        LinkedPushConfigurationDocumentV1.model_validate(changed)


@pytest.mark.parametrize(
    "field,value",
    [
        ("can_push_video", dict(presence="null", value=None)),
        ("is_gpppa", dict(presence="present", value=True)),
        ("available_status", "unknown"),
    ],
)
def test_available_or_customer_consent_cannot_replace_capability(field: str, value: Any) -> None:
    saved = document()
    changed = saved.model_dump()
    changed["identity_observation"][field] = value
    observation = IdentityInfoObservationV1.model_validate(changed["identity_observation"])
    changed["configuration"]["identity_observation_digest"] = observation.digest()
    config = LinkedPushConfigurationV1.model_validate(changed["configuration"])
    changed["configuration_digest"] = fingerprint(
        "inlet.tiktok-linked-push-configuration-fields.v1", config.model_dump(mode="json")
    )
    with pytest.raises(ValidationError):
        LinkedPushConfigurationDocumentV1.model_validate(changed)


def test_literal_numeric_answer_and_live_rejected() -> None:
    saved = document().model_dump()
    saved["answer"]["commercial_music_rights_reviewed"] = 1
    with pytest.raises(ValidationError):
        LinkedPushConfigurationDocumentV1.model_validate(saved)
    saved = document().model_dump()
    saved["environment"] = "live"
    with pytest.raises(ValidationError):
        LinkedPushConfigurationDocumentV1.model_validate(saved)


def test_fresh_unchanged_capabilities_do_not_require_clock_digest_reconsent() -> None:
    from app.publication.tiktok_linked_review_service import current_capabilities
    from fastapi import HTTPException

    saved = document()
    fresh_now = NOW + timedelta(minutes=1)
    identity = IdentityInfoObservationV1.model_validate(
        {
            **saved.identity_observation.model_dump(),
            "observed_at": fresh_now,
            "expires_at": fresh_now + timedelta(minutes=5),
        }
    )
    advertiser = AdvertiserCapabilitiesObservationV1.model_validate(
        {
            **saved.advertiser_observation.model_dump(),
            "observed_at": fresh_now,
            "expires_at": fresh_now + timedelta(minutes=5),
        }
    )
    assert identity.digest() != saved.configuration.identity_observation_digest
    current_capabilities(saved, identity, advertiser, fresh_now)
    changed = IdentityInfoObservationV1.model_validate(
        {**identity.model_dump(), "can_push_video": dict(presence="present", value=False)}
    )
    with pytest.raises(HTTPException, match="current_linked_capabilities_unavailable"):
        current_capabilities(saved, changed, advertiser, fresh_now)
    with pytest.raises(HTTPException, match="current_linked_capabilities_unavailable"):
        current_capabilities(saved, identity, advertiser, identity.expires_at)
