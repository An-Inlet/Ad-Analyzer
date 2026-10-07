"""Separate linked-post customer consent; never reinterpret social v1/v2 approval."""

from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.goals.schemas import StrictModel
from app.publication.contracts import fingerprint
from app.publication.provider_contracts import Digest
from app.publication.social_catalog import SocialCatalogRequest
from app.publication.social_review_contracts import SocialRequirements
from app.publication.tiktok_linked_contracts import (
    AdvertiserCapabilitiesObservationV1,
    IdentityInfoObservationV1,
    LinkedOwnerV1,
)
from app.publication.tiktok_linked_plan import LinkedPushConfigurationV1


class LinkedPushCustomerAnswerV1(StrictModel):
    """Customer declarations are consent, not provider capability evidence."""

    kind: Literal["tiktok_linked_push"] = "tiktok_linked_push"
    reviewed_video_and_cover: Literal[True]
    commercial_music_rights_reviewed: Literal[True]
    creates_new_linked_post_reviewed: Literal[True]
    ads_only_visibility_reviewed: Literal[True]

    @field_validator(
        "reviewed_video_and_cover",
        "commercial_music_rights_reviewed",
        "creates_new_linked_post_reviewed",
        "ads_only_visibility_reviewed",
        mode="before",
    )
    @classmethod
    def explicit_true(cls, value: object) -> object:
        if value is not True:
            raise ValueError("explicit customer confirmation required")
        return value


class LinkedPushConfigurationDocumentV1(StrictModel):
    schema_version: Literal["inlet.tiktok-linked-push-configuration-review.v1"] = (
        "inlet.tiktok-linked-push-configuration-review.v1"
    )
    request: SocialCatalogRequest
    environment: Literal["contract_test"]
    option_id: Digest
    identity_label: str = Field(min_length=1, max_length=160)
    requirements: SocialRequirements
    answer: LinkedPushCustomerAnswerV1
    identity_observation: IdentityInfoObservationV1
    advertiser_observation: AdvertiserCapabilitiesObservationV1
    configuration: LinkedPushConfigurationV1
    configuration_digest: Digest

    def rights_digest(self) -> str:
        return linked_rights_digest(
            self.request, self.requirements, self.answer, self.configuration
        )

    @model_validator(mode="after")
    def exact(self) -> "LinkedPushConfigurationDocumentV1":
        account = self.request.account
        owner = LinkedOwnerV1(
            workspace_id=account.workspace_id,
            account_id=account.account.account_id,
            connection_id=account.account.connection_id,
            external_advertiser_id=account.external_advertiser_id,
            connection_version=account.connection_version,
        )
        identity, advertiser, config = (
            self.identity_observation,
            self.advertiser_observation,
            self.configuration,
        )
        if (
            account.account.platform != "tiktok_ads"
            or identity.request.owner != owner
            or advertiser.request.owner != owner
            or identity.request.identity != config.identity
            or identity.available_status != "AVAILABLE"
            or identity.is_gpppa.presence != "present"
            or identity.is_gpppa.value is not False
            or identity.can_push_video.presence != "present"
            or identity.can_push_video.value is not True
            or config.identity_observation_digest != identity.digest()
            or config.advertiser_observation_digest != advertiser.digest()
            or config.rights_review_digest != self.rights_digest()
            or self.configuration_digest
            != fingerprint(
                "inlet.tiktok-linked-push-configuration-fields.v1", config.model_dump(mode="json")
            )
            or not self.requirements.wording
            or not self.requirements.wording.strip()
        ):
            raise ValueError("exact owned linked configuration and declarations required")
        # No OFF branch: omitted/null ads-only capabilities cannot become false.
        # BC owner publishing permission still requires independent runtime qualification;
        # this document and can_push_video alone never confer it.
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


def linked_rights_digest(
    request: SocialCatalogRequest,
    requirements: SocialRequirements,
    answer: LinkedPushCustomerAnswerV1,
    configuration: LinkedPushConfigurationV1,
) -> str:
    return fingerprint(
        "inlet.tiktok-linked-push-customer-rights.v1",
        {
            "request": request.model_dump(mode="json"),
            "requirements": requirements.model_dump(mode="json"),
            "answer": answer.model_dump(mode="json"),
            "video": configuration.video.model_dump(mode="json"),
            "cover": configuration.cover.model_dump(mode="json"),
            "identity": configuration.identity.model_dump(mode="json"),
        },
    )
