"""Lossless, immutable request-bound post facts with no eligibility promotion."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from app.collectors.tiktok_linked_posts import parse_linked_posts_page
from app.collectors.tiktok_linked_posts_contracts import (
    LinkedPostsCatalogV1,
    LinkedPostsPageRequestV1,
    LinkedPostsRequestV1,
    cursor_integer,
)
from app.collectors.tiktok_owned_discovery import TikTokDiscoveryUnavailable
from app.publication.tiktok_linked_contracts import LinkedOwnerV1, TikTokBusinessIdentityV1
from pydantic import ValidationError


def request() -> LinkedPostsPageRequestV1:
    return LinkedPostsPageRequestV1(
        request=LinkedPostsRequestV1(
            owner=LinkedOwnerV1(
                workspace_id=1,
                account_id=2,
                connection_id=3,
                external_advertiser_id="123",
                connection_version="generation-4",
            ),
            identity=TikTokBusinessIdentityV1(
                identity_type="BC_AUTH_TT", identity_id="linked-1", identity_authorized_bc_id="bc-1"
            ),
            exclude_adsonly=False,
            count=20,
        )
    )


def body(
    *, cursor: str = "900719925474099312345", more: bool = False, identifier: str = "post-1"
) -> dict[str, Any]:
    return {
        "code": 0,
        "data": {
            "cursor": cursor,
            "has_more": more,
            "video_list": [
                {
                    "item_id": identifier,
                    "item_type": "VIDEO",
                    "text": "Exact inherited post caption",
                    "status": "PROVIDER_VISIBILITY_VALUE",
                    "auth_info": None,
                    "anchor_list": {},
                    "video_info": {
                        "duration": Decimal("12.123456789012345678901"),
                        "height": 1920,
                        "width": 1080,
                        "size": 123456,
                        "bit_rate": 456789,
                        "format": "mp4",
                        "url": "https://media.example/private-token",
                        "signature": "discard-me",
                        "poster_url": "https://media.example/poster?x-expires=9999999999",
                    },
                }
            ],
        },
    }


def test_exact_request_binding_lossless_scalars_and_private_url_omission() -> None:
    parsed = parse_linked_posts_page(request(), body())
    post = parsed.posts[0]
    assert post.request == request().request
    assert parsed.cursor == "900719925474099312345"
    assert cursor_integer(parsed.cursor) == 900719925474099312345
    assert post.video_info.value is not None
    assert post.video_info.value.duration.value == Decimal("12.123456789012345678901")
    raw = parsed.model_dump_json()
    assert "private-token" not in raw and "discard-me" not in raw and "x-expires" not in raw
    assert "video_id" not in raw and "auth_info" not in raw and "anchor_list" not in raw
    assert type(parsed).model_validate_json(raw) == parsed
    assert post.publication_eligibility == "not_assessed"
    with pytest.raises(ValidationError):
        post.request.owner.workspace_id = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    "field,value",
    [
        ("cursor", 123),
        ("cursor", "1.5"),
        ("cursor", "01"),
        ("cursor", "-0"),
        ("cursor", "1e10"),
        ("cursor", None),
        ("has_more", 1),
        ("has_more", None),
        ("video_list", None),
        ("video_list", {}),
    ],
)
def test_malformed_page_is_not_empty_complete(field: str, value: object) -> None:
    payload = body()
    payload["data"][field] = value
    with pytest.raises(TikTokDiscoveryUnavailable):
        parse_linked_posts_page(request(), payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("item_id", 123),
        ("item_type", "CAROUSEL"),
        ("text", []),
        ("status", False),
        ("video_info", []),
        ("anchor_list", []),
        ("auth_info", []),
    ],
)
def test_unsupported_row_shape_does_not_gain_authority(field: str, value: object) -> None:
    payload = body()
    payload["data"]["video_list"][0][field] = value
    with pytest.raises(TikTokDiscoveryUnavailable):
        parse_linked_posts_page(request(), payload)


def test_absence_and_null_are_distinct_facts() -> None:
    payload = body()
    row = payload["data"]["video_list"][0]
    del row["text"]
    row["status"] = None
    row["video_info"] = None
    post = parse_linked_posts_page(request(), payload).posts[0]
    assert post.text.presence == "absent" and post.text.value is None
    assert post.status.presence == "null" and post.status.value is None
    assert post.video_info.presence == "null"


def test_decreasing_cursor_is_valid_but_cycles_duplicates_and_partial_views_are_not() -> None:
    initial = request()
    first = parse_linked_posts_page(initial, body(cursor="100", more=True))
    second_request = LinkedPostsPageRequestV1(request=initial.request, cursor=100)
    last = parse_linked_posts_page(second_request, body(cursor="99", identifier="post-2"))
    now = datetime(2026, 10, 7, tzinfo=UTC)
    values = dict(
        request=initial.request,
        pages=(first, last),
        observed_started_at=now,
        observed_ended_at=now,
        expires_at=now + timedelta(minutes=5),
        coverage="identity_video_view",
    )
    catalog = LinkedPostsCatalogV1.model_validate(values)
    assert catalog.traversal_completeness == "complete_requested_view"
    assert catalog.snapshot_consistency == "not_established"
    assert (
        catalog.publication_eligibility == "not_assessed" and catalog.spending_authority == "none"
    )
    for pages in ((first,), (first, last.model_copy(update={"posts": first.posts}))):
        with pytest.raises(ValidationError):
            LinkedPostsCatalogV1.model_validate({**values, "pages": pages})
    with pytest.raises(TikTokDiscoveryUnavailable):
        parse_linked_posts_page(second_request, body(cursor="100", more=True))


def test_empty_terminal_page_valid_but_empty_continuation_unavailable() -> None:
    payload = body()
    payload["data"]["video_list"] = []
    assert parse_linked_posts_page(request(), payload).posts == ()
    payload["data"]["has_more"] = True
    with pytest.raises(TikTokDiscoveryUnavailable):
        parse_linked_posts_page(request(), payload)
