"""Bounded in-memory collection; the caller owns authorization and atomic storage."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Protocol

from app.campaign_performance.presence_contracts import _canonical
from app.campaign_performance.selected_contracts import (
    MAX_SELECTED_BYTES,
    MAX_SELECTED_FACTS,
    SelectedCampaignDayV1,
    SelectedCaptureRequestV1,
    SelectedCaptureV1,
    capture_request_digest,
)
from app.google_connections.selected_http import GoogleSelectedReadUnavailable
from app.google_connections.selected_presence import GoogleSelectedPageV1, parse_selected_page


class SelectedPageReader(Protocol):
    def __call__(
        self,
        request: SelectedCaptureRequestV1,
        campaign_mapping: dict[str, int],
        /,
        *,
        requested_cursor: str = "",
    ) -> GoogleSelectedPageV1: ...


class GoogleSelectedCollectionUnavailable(ValueError):
    """No partial graph or provider error is exposed."""


def collect_google_selected_capture(
    request: SelectedCaptureRequestV1,
    campaign_mapping: dict[str, int],
    read_page: SelectedPageReader,
    revalidate: Callable[[SelectedCaptureRequestV1], None],
    clock: Callable[[], datetime],
) -> SelectedCaptureV1:
    try:
        req = SelectedCaptureRequestV1.model_validate(request)
        mapping = dict(campaign_mapping)
        # Reuse exact profile/strict mapping validation before any reader or callback.
        parse_selected_page(b"{}", req, mapping)
        expected = capture_request_digest(req)
        deadline = monotonic() + 60
        expires = req.started_at + timedelta(seconds=60)

        def now() -> datetime:
            value = clock()
            if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("aware server clock required")
            return value.astimezone(UTC)

        def time_check() -> datetime:
            value = now()
            if not req.started_at <= value < expires or monotonic() >= deadline:
                raise ValueError("selected collection expired")
            return value

        def check() -> datetime:
            time_check()
            revalidate(req)
            return time_check()

        facts: list[SelectedCampaignDayV1] = []
        keys: set[tuple[int, object]] = set()
        cursors: set[str] = set()
        cursor = ""
        measured = len(_canonical(req))
        for page_number in range(1, 101):
            check()
            page = GoogleSelectedPageV1.model_validate(
                read_page(req, dict(mapping), requested_cursor=cursor)
            )
            check()
            if (page.capture_id, page.request_digest) != (req.capture_id, expected):
                raise ValueError("selected page binding changed")
            for fact in page.facts:
                key = (fact.campaign_id, fact.metric_date)
                if (
                    key in keys
                    or mapping.get(fact.native_campaign_id) != fact.campaign_id
                    or not req.requested_starts_on <= fact.metric_date <= req.requested_ends_on
                ):
                    raise ValueError("selected page facts changed")
                keys.add(key)
                facts.append(fact)
                measured += len(_canonical(fact)) + 1
                if len(facts) > MAX_SELECTED_FACTS or measured > MAX_SELECTED_BYTES:
                    raise ValueError("selected collection capacity exceeded")
            following = page.following_cursor
            if not following:
                completed = check()
                result = SelectedCaptureV1(
                    request=req,
                    request_digest=expected,
                    completed_at=completed,
                    capability="supported",
                    pagination_complete=True,
                    page_count=page_number,
                    facts=tuple(facts),
                )
                check()
                return result
            if following == cursor or following in cursors:
                raise ValueError("selected cursor cycle")
            cursors.add(following)
            cursor = following
        raise ValueError("selected page bound")
    except (
        GoogleSelectedReadUnavailable,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        ArithmeticError,
    ):
        raise GoogleSelectedCollectionUnavailable(
            "google_selected_collection_unavailable"
        ) from None
