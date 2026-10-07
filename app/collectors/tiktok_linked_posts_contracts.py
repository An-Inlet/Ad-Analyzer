"""Request-bound linked VIDEO facts, never post/ad eligibility or financial proof."""

from datetime import timedelta
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, model_validator

from app.publication.contracts import fingerprint
from app.publication.tiktok_linked_contracts import (
    Frozen,
    LinkedIdentityV1,
    LinkedOwnerV1,
    ProviderId,
)

Cursor = Annotated[str, Field(min_length=1, max_length=65, pattern=r"^-?(0|[1-9][0-9]{0,63})$")]


def cursor_integer(value: str) -> int:
    """No float conversion; retain the provider string separately in the page."""
    if not isinstance(value, str) or len(value) > 65:
        raise ValueError("unsupported linked post cursor")
    result = int(value)
    if str(result) != value:
        raise ValueError("noncanonical linked post cursor")
    return result


class LinkedPostsRequestV1(Frozen):
    schema_version: Literal["inlet.tiktok-linked-posts-request.v1"] = (
        "inlet.tiktok-linked-posts-request.v1"
    )
    owner: LinkedOwnerV1
    identity: LinkedIdentityV1
    item_type: Literal["VIDEO"] = "VIDEO"
    exclude_adsonly: bool
    count: int = Field(ge=1, le=20)

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class LinkedPostsPageRequestV1(Frozen):
    request: LinkedPostsRequestV1
    cursor: int | None = Field(default=None, ge=-(10**64 - 1), le=10**64 - 1)


class ObservedPostTextV1(Frozen):
    presence: Literal["absent", "null", "present"]
    value: str | None = Field(max_length=16384)

    @model_validator(mode="after")
    def bound(self) -> "ObservedPostTextV1":
        if (self.presence == "present") != (self.value is not None):
            raise ValueError("post text presence mismatch")
        return self


class ObservedPostIntegerV1(Frozen):
    presence: Literal["absent", "null", "present"]
    value: int | None = Field(ge=0, le=10**18)

    @model_validator(mode="after")
    def bound(self) -> "ObservedPostIntegerV1":
        if (self.presence == "present") != (self.value is not None):
            raise ValueError("post integer presence mismatch")
        return self


class ObservedPostNumberV1(Frozen):
    presence: Literal["absent", "null", "present"]
    value: Decimal | None = Field(ge=0, le=10**18, allow_inf_nan=False)

    @model_validator(mode="after")
    def bound(self) -> "ObservedPostNumberV1":
        if (self.presence == "present") != (self.value is not None):
            raise ValueError("post number presence mismatch")
        return self


class LinkedVideoInfoV1(Frozen):
    # Native scalars, without conversion or inferred ad-format qualification.
    bit_rate: ObservedPostIntegerV1
    size: ObservedPostIntegerV1
    height: ObservedPostIntegerV1
    width: ObservedPostIntegerV1
    duration: ObservedPostNumberV1
    format: ObservedPostTextV1


class ObservedVideoInfoV1(Frozen):
    presence: Literal["absent", "null", "present"]
    value: LinkedVideoInfoV1 | None

    @model_validator(mode="after")
    def bound(self) -> "ObservedVideoInfoV1":
        if (self.presence == "present") != (self.value is not None):
            raise ValueError("video info presence mismatch")
        return self


class LinkedVideoPostV1(Frozen):
    schema_version: Literal["inlet.tiktok-linked-video-post.v1"] = (
        "inlet.tiktok-linked-video-post.v1"
    )
    request: LinkedPostsRequestV1
    item_id: ProviderId
    item_type: Literal["VIDEO"]
    text: ObservedPostTextV1
    status: ObservedPostTextV1
    video_info: ObservedVideoInfoV1
    identity_binding: Literal["request_context_only"] = "request_context_only"
    publication_eligibility: Literal["not_assessed"] = "not_assessed"

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class LinkedPostsPageV1(Frozen):
    request: LinkedPostsPageRequestV1
    cursor: Cursor
    has_more: bool
    posts: tuple[LinkedVideoPostV1, ...] = Field(max_length=20)

    @model_validator(mode="after")
    def bound(self) -> "LinkedPostsPageV1":
        cursor_integer(self.cursor)
        if (
            len(self.posts) > self.request.request.count
            or len({p.item_id for p in self.posts}) != len(self.posts)
            or any(p.request != self.request.request for p in self.posts)
            or (self.has_more and not self.posts)
            or (self.has_more and self.request.cursor == cursor_integer(self.cursor))
        ):
            raise ValueError("linked post page incomplete or inconsistent")
        return self


class LinkedPostsCatalogV1(Frozen):
    schema_version: Literal["inlet.tiktok-linked-posts-catalog.v1"] = (
        "inlet.tiktok-linked-posts-catalog.v1"
    )
    request: LinkedPostsRequestV1
    environment: Literal["contract_test"] = "contract_test"
    observed_started_at: AwareDatetime
    observed_ended_at: AwareDatetime
    expires_at: AwareDatetime
    pages: tuple[LinkedPostsPageV1, ...] = Field(min_length=1, max_length=25)
    traversal_completeness: Literal["complete_requested_view"] = "complete_requested_view"
    coverage: Literal["identity_video_view", "latest_500_organic"]
    snapshot_consistency: Literal["not_established"] = "not_established"
    publication_eligibility: Literal["not_assessed"] = "not_assessed"
    spending_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def complete(self) -> "LinkedPostsCatalogV1":
        if not (
            self.observed_started_at
            <= self.observed_ended_at
            < self.expires_at
            <= self.observed_started_at + timedelta(minutes=5)
        ):
            raise ValueError("linked post observation interval invalid")
        expected = "latest_500_organic" if self.request.exclude_adsonly else "identity_video_view"
        if self.coverage != expected:
            raise ValueError("linked post coverage mismatch")
        cursor: int | None = None
        seen_cursors: set[int] = set()
        seen_posts: set[str] = set()
        for index, page in enumerate(self.pages):
            if (
                page.request.request != self.request
                or page.request.cursor != cursor
                or page.has_more != (index < len(self.pages) - 1)
            ):
                raise ValueError("linked post traversal incomplete")
            for post in page.posts:
                if post.item_id in seen_posts:
                    raise ValueError("linked post repeated")
                seen_posts.add(post.item_id)
            cursor = cursor_integer(page.cursor)
            if page.has_more:
                if cursor in seen_cursors:
                    raise ValueError("linked post cursor cycle")
                seen_cursors.add(cursor)
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))
