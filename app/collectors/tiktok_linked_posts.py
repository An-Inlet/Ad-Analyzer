"""Strict linked VIDEO decoding; request binding is not provider eligibility."""

from decimal import Decimal
from typing import Any, Literal

from app.collectors.tiktok_discovery_parser import object_value
from app.collectors.tiktok_linked_posts_contracts import (
    LinkedPostsPageRequestV1,
    LinkedPostsPageV1,
    LinkedVideoInfoV1,
    LinkedVideoPostV1,
    ObservedPostIntegerV1,
    ObservedPostNumberV1,
    ObservedPostTextV1,
    ObservedVideoInfoV1,
)
from app.collectors.tiktok_owned_discovery import unavailable


def presence(row: dict[str, Any], field: str) -> Literal["absent", "null", "present"]:
    return "absent" if field not in row else "null" if row[field] is None else "present"


def observed_text(row: dict[str, Any], field: str) -> ObservedPostTextV1:
    return ObservedPostTextV1(presence=presence(row, field), value=row.get(field))


def video_info(row: dict[str, Any]) -> ObservedVideoInfoV1:
    state = presence(row, "video_info")
    if state != "present":
        return ObservedVideoInfoV1(presence=state, value=None)
    raw = object_value(row["video_info"])
    for name in ("poster_url", "signature", "url"):
        value = raw.get(name)
        if value is not None and (type(value) is not str or len(value) > 16384):
            raise unavailable()
    duration = raw.get("duration")
    # The owned HTTP decoder uses Decimal, not binary floats. No string/boolean
    # coercion or unsupported claim that previously rounded JSON was lossless.
    if duration is not None and type(duration) not in (int, Decimal):
        raise unavailable()
    return ObservedVideoInfoV1(
        presence="present",
        value=LinkedVideoInfoV1(
            **{
                name: ObservedPostIntegerV1(presence=presence(raw, name), value=raw.get(name))
                for name in ("bit_rate", "size", "height", "width")
            },
            duration=ObservedPostNumberV1(
                presence=presence(raw, "duration"),
                value=Decimal(duration) if duration is not None else None,
            ),
            format=observed_text(raw, "format"),
        ),
    )


def parse_linked_posts_page(
    request: LinkedPostsPageRequestV1, payload: object
) -> LinkedPostsPageV1:
    """Accept a losslessly decoded object. No default rows/cursor/status on absence."""
    try:
        request = LinkedPostsPageRequestV1.model_validate_json(request.model_dump_json())
        envelope = object_value(payload)
        if type(envelope.get("code")) is not int or envelope["code"] != 0:
            raise unavailable()
        data = object_value(envelope.get("data"))
        rows = data.get("video_list")
        if not isinstance(rows, list) or len(rows) > request.request.count:
            raise unavailable()
        posts = []
        for value in rows:
            row = object_value(value)
            for optional_object in ("anchor_list", "auth_info"):
                if row.get(optional_object) is not None:
                    object_value(row[optional_object])
            posts.append(
                LinkedVideoPostV1(
                    request=request.request,
                    item_id=row["item_id"],
                    item_type=row["item_type"],
                    text=observed_text(row, "text"),
                    status=observed_text(row, "status"),
                    video_info=video_info(row),
                )
            )
        return LinkedPostsPageV1(
            request=request,
            cursor=data["cursor"],
            has_more=data["has_more"],
            posts=tuple(posts),
        )
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
        raise unavailable() from None
