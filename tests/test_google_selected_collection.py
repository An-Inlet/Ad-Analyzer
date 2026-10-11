"""Terminal selected graphs over raw MockHTTP; no live capability assertion."""

import json
from datetime import timedelta
from typing import Any

import httpx
import pytest
from app.campaign_performance.selected_contracts import capture_request_digest
from app.google_connections.selected_collection import (
    GoogleSelectedCollectionUnavailable,
    collect_google_selected_capture,
)
from app.google_connections.selected_http import GoogleSelectedHTTPRead
from app.google_connections.selected_presence import GoogleSelectedPageV1, parse_selected_page

from tests.test_google_selected_http import context, response
from tests.test_selected_raw_observations import google_request, google_row

START = google_request().started_at


def test_real_read_pages_complete_zero_and_positive_without_writes() -> None:
    seen = []

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/googleAds:search")
        body = json.loads(request.content)
        seen.append(body)
        data = response(body["query"])
        if "FROM campaign" in body["query"]:
            row = google_row()
            if not body["pageToken"]:
                row["segments"]["date"] = "2026-09-29"
                row["metrics"]["conversions"] = "0"
                data = {"results": [row], "nextPageToken": "next"}
            else:
                data = {"results": [row]}
        return httpx.Response(200, json=data)

    reader = GoogleSelectedHTTPRead(
        lambda request: context(),
        lambda request: None,
        transport=httpx.MockTransport(handle),
        clock=lambda: START,
    )
    capture = collect_google_selected_capture(
        google_request(), {"555": 5}, reader, lambda r: None, lambda: START
    )
    assert capture.page_count == 2 and len(seen) == 6
    assert [f.selected_conversions.value for f in capture.facts] == [0, 10]
    assert all(f.selected_conversions.presence == "present" for f in capture.facts)
    assert capture.spending_authorized is False


def page(*, cursor: str = "", rows: list[dict[str, Any]] | None = None) -> GoogleSelectedPageV1:
    return parse_selected_page(
        json.dumps({"results": rows or [], "nextPageToken": cursor}).encode(),
        google_request(),
        {"555": 5},
    )


def test_terminal_empty_is_no_observations_and_mapping_is_snapshotted() -> None:
    mapping = {"555": 5}
    calls = 0

    def read(request: Any, supplied: dict[str, int], *, requested_cursor: str = "") -> Any:
        nonlocal calls
        calls += 1
        assert supplied == {"555": 5}
        mapping.clear()
        supplied.clear()
        return page(cursor="next" if calls == 1 else "")

    capture = collect_google_selected_capture(
        google_request(), mapping, read, lambda r: None, lambda: START
    )
    assert capture.facts == () and capture.page_count == 2


@pytest.mark.parametrize("bad", ["duplicate", "cycle", "binding", "mapping", "date", "copy"])
def test_malformed_cross_page_graph_never_completes(bad: str) -> None:
    calls = 0

    def read(request: Any, supplied: dict[str, int], *, requested_cursor: str = "") -> Any:
        nonlocal calls
        calls += 1
        original = page(rows=[google_row()])
        if bad == "duplicate":
            return original.model_copy(update={"following_cursor": "next" if calls == 1 else ""})
        if bad == "cycle":
            return page(cursor="next" if calls % 2 else "other")
        if bad == "binding":
            return page().model_copy(update={"request_digest": "d" * 64})
        changes: dict[str, dict[str, Any]] = {
            "mapping": {"campaign_id": 9},
            "date": {"metric_date": google_request().requested_starts_on - timedelta(days=1)},
            "copy": {"campaign_id": True},
        }
        return original.model_copy(
            update={"facts": (original.facts[0].model_copy(update=changes[bad]),)}
        )

    with pytest.raises(GoogleSelectedCollectionUnavailable):
        collect_google_selected_capture(
            google_request(), {"555": 5}, read, lambda r: None, lambda: START
        )


def test_page_bound_discards_partial_collection() -> None:
    calls = 0

    def read(request: Any, supplied: dict[str, int], *, requested_cursor: str = "") -> Any:
        nonlocal calls
        calls += 1
        return page(cursor=str(calls))

    with pytest.raises(GoogleSelectedCollectionUnavailable):
        collect_google_selected_capture(
            google_request(), {"555": 5}, read, lambda r: None, lambda: START
        )
    assert calls == 100


@pytest.mark.parametrize("bound", ["MAX_SELECTED_FACTS", "MAX_SELECTED_BYTES"])
def test_whole_collection_capacity_before_terminal_return(
    monkeypatch: pytest.MonkeyPatch, bound: str
) -> None:
    monkeypatch.setattr(f"app.google_connections.selected_collection.{bound}", 1)
    prior = google_row()
    prior["segments"]["date"] = "2026-09-29"

    def read(request: Any, supplied: dict[str, int], *, requested_cursor: str = "") -> Any:
        return page(rows=[prior, google_row()])

    with pytest.raises(GoogleSelectedCollectionUnavailable):
        collect_google_selected_capture(
            google_request(), {"555": 5}, read, lambda r: None, lambda: START
        )


@pytest.mark.parametrize("stage", ["authorization", "read", "final", "naive", "future"])
def test_deadlines_after_blocking_boundaries(stage: str) -> None:
    current = START
    checks = reads = 0

    def validate(request: Any) -> None:
        nonlocal current, checks
        checks += 1
        if stage == "authorization" or (stage == "final" and checks == 4):
            current = START + timedelta(seconds=60)

    def read(request: Any, supplied: dict[str, int], *, requested_cursor: str = "") -> Any:
        nonlocal current, reads
        reads += 1
        if stage == "read":
            current = START + timedelta(seconds=60)
        return page()

    if stage == "naive":
        current = START.replace(tzinfo=None)
    if stage == "future":
        current = START - timedelta(microseconds=1)
    with pytest.raises(GoogleSelectedCollectionUnavailable):
        collect_google_selected_capture(
            google_request(), {"555": 5}, read, validate, lambda: current
        )
    if stage in {"authorization", "naive", "future"}:
        assert reads == 0


def test_elapsed_monotonic_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    ticks = iter([0.0, 61.0])
    monkeypatch.setattr("app.google_connections.selected_collection.monotonic", lambda: next(ticks))

    def unexpected(request: Any, supplied: dict[str, int], *, requested_cursor: str = "") -> Any:
        raise AssertionError("expired collection must not read")

    with pytest.raises(GoogleSelectedCollectionUnavailable):
        collect_google_selected_capture(
            google_request(), {"555": 5}, unexpected, lambda r: None, lambda: START
        )


def test_request_digest_and_partial_page_failure_are_not_published() -> None:
    first = page(cursor="next", rows=[google_row()])
    calls = 0

    def read(request: Any, supplied: dict[str, int], *, requested_cursor: str = "") -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            assert first.request_digest == capture_request_digest(request)
            return first
        raise ValueError("private upstream details")

    with pytest.raises(
        GoogleSelectedCollectionUnavailable, match="^google_selected_collection_unavailable$"
    ):
        collect_google_selected_capture(
            google_request(), {"555": 5}, read, lambda r: None, lambda: START
        )
