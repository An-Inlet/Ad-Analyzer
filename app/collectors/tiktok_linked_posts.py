"""Strict linked VIDEO decoding; request binding is not provider eligibility."""

import json
from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal
from time import monotonic
from typing import Any, Literal

import httpx
from pydantic import SecretStr

from app.collectors.tiktok_discovery_parser import object_value
from app.collectors.tiktok_linked_posts_contracts import (
    LinkedPostsCatalogV1,
    LinkedPostsPageRequestV1,
    LinkedPostsPageV1,
    LinkedPostsRequestV1,
    LinkedVideoInfoV1,
    LinkedVideoPostV1,
    ObservedPostIntegerV1,
    ObservedPostNumberV1,
    ObservedPostTextV1,
    ObservedVideoInfoV1,
    cursor_integer,
)
from app.collectors.tiktok_owned_discovery import _nonfinite, _unique_object, unavailable
from app.production_runtime.owned_tiktok_contexts import OwnedTikTokContexts
from app.publication.execution_contracts import ExecutionAccount
from app.publication.tiktok_linked_contracts import LinkedIdentityV1, LinkedOwnerV1

MAX_PAGES = 25
MAX_PAGE_BYTES = 2_000_000
MAX_TOTAL_BYTES = 8_000_000
MAX_SECONDS = 30
ENDPOINT = "https://business-api.tiktok.com/open_api/v1.3/identity/video/get/"


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


class TikTokLinkedPosts:
    """Owned, bounded native GETs; construction never opens provider sockets."""

    def __init__(
        self,
        scope: ExecutionAccount,
        contexts: OwnedTikTokContexts,
        transport: httpx.MockTransport,
        clock: Callable[[], datetime],
    ) -> None:
        if (
            not isinstance(transport, httpx.MockTransport)
            or contexts.manifest.environment != "contract_test"
            or scope.account.platform != "tiktok_ads"
        ):
            raise unavailable()
        self._scope = ExecutionAccount.model_validate_json(scope.model_dump_json())
        self.owner = LinkedOwnerV1(
            workspace_id=self._scope.workspace_id,
            account_id=self._scope.account.account_id,
            connection_id=self._scope.account.connection_id,
            external_advertiser_id=self._scope.external_advertiser_id,
            connection_version=self._scope.connection_version,
        )
        self.contexts, self.transport, self.clock = contexts, transport, clock

    def videos(
        self,
        identity: LinkedIdentityV1,
        *,
        exclude_adsonly: bool,
        count: int = 20,
    ) -> LinkedPostsCatalogV1:
        started, deadline = self.clock(), monotonic() + MAX_SECONDS
        expiry: datetime | None = None
        original_token: SecretStr | None = None
        total_bytes = 0

        def remaining() -> float:
            current, seconds = self.clock(), deadline - monotonic()
            if (
                started.tzinfo is None
                or current.tzinfo is None
                or current < started
                or seconds <= 0
                or (expiry is not None and current >= expiry)
            ):
                raise unavailable()
            return seconds

        def checkpoint() -> SecretStr:
            nonlocal expiry, original_token
            remaining()
            token, credential_expiry = self.contexts.credentials(self._scope)
            if credential_expiry.tzinfo is None:
                raise unavailable()
            if original_token is None:
                original_token = token
                expiry = min(credential_expiry, started + timedelta(minutes=5))
            elif token != original_token:
                raise unavailable()
            assert expiry is not None
            expiry = min(expiry, credential_expiry)
            remaining()
            return token

        pages: list[LinkedPostsPageV1] = []
        seen_cursors: set[int] = set()
        seen_posts: set[str] = set()
        try:
            with httpx.Client(
                transport=self.transport,
                follow_redirects=False,
                trust_env=False,
                headers={"Accept": "application/json", "Accept-Encoding": "identity"},
            ) as client:
                request = LinkedPostsRequestV1.model_validate_json(
                    LinkedPostsRequestV1(
                        owner=self.owner,
                        identity=identity,
                        exclude_adsonly=exclude_adsonly,
                        count=count,
                    ).model_dump_json()
                )
                page_request = LinkedPostsPageRequestV1(request=request)
                for _ in range(MAX_PAGES):
                    token = checkpoint()
                    params: dict[str, Any] = {
                        "advertiser_id": request.owner.external_advertiser_id,
                        **request.identity.model_dump(),
                        "item_type": "VIDEO",
                        "count": request.count,
                        "exclude_adsonly": request.exclude_adsonly,
                    }
                    if page_request.cursor is not None:
                        params["cursor"] = page_request.cursor
                    seconds = remaining()
                    with client.stream(
                        "GET",
                        ENDPOINT,
                        params=params,
                        headers={"Access-Token": token.get_secret_value()},
                        timeout=httpx.Timeout(seconds, connect=min(5, seconds)),
                    ) as response:
                        remaining()
                        if response.status_code != 200:
                            raise unavailable()
                        raw = bytearray()
                        for chunk in response.iter_bytes():
                            remaining()
                            total_bytes += len(chunk)
                            if (
                                len(raw) + len(chunk) > MAX_PAGE_BYTES
                                or total_bytes > MAX_TOTAL_BYTES
                            ):
                                raise unavailable()
                            raw.extend(chunk)
                        payload = json.loads(
                            raw,
                            parse_float=Decimal,
                            parse_constant=_nonfinite,
                            object_pairs_hook=_unique_object,
                        )
                    checkpoint()
                    page = parse_linked_posts_page(page_request, payload)
                    for post in page.posts:
                        if post.item_id in seen_posts:
                            raise unavailable()
                        seen_posts.add(post.item_id)
                    pages.append(page)
                    if not page.has_more:
                        break
                    cursor = cursor_integer(page.cursor)
                    if cursor in seen_cursors:
                        raise unavailable()
                    seen_cursors.add(cursor)
                    page_request = LinkedPostsPageRequestV1(request=request, cursor=cursor)
                else:
                    raise unavailable()
            checkpoint()  # Transport close and its possible authority changes precede return.
            assert expiry is not None
            return LinkedPostsCatalogV1(
                request=request,
                pages=tuple(pages),
                observed_started_at=started,
                observed_ended_at=self.clock(),
                expires_at=expiry,
                coverage="latest_500_organic" if request.exclude_adsonly else "identity_video_view",
            )
        except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
            raise unavailable() from None
