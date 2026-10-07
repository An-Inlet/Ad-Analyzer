"""Customer intent only; no native identity, provider facts or spending proof inputs."""

from app.publication.provider_contracts import Digest, Id
from app.publication.social_selection import CatalogIntent
from app.publication.tiktok_linked_review_contracts import LinkedPushCustomerAnswerV1


class LinkedPushReviewIntent(CatalogIntent):
    option_id: Digest
    cover_media_id: Id
    answer: LinkedPushCustomerAnswerV1
