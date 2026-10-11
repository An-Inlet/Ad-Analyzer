import json
from datetime import timedelta
from typing import Any

import httpx
import pytest
from app.google_connections.selected_catalog import (
    GoogleReportingCatalogContext,
    GoogleReportingCatalogHTTP,
    GoogleReportingCatalogRequestV1,
    GoogleReportingCatalogUnavailable,
    GoogleReportingCatalogV1,
)
from pydantic import SecretStr, ValidationError

from tests.test_google_selected_http import NOW, response
from tests.test_selected_raw_observations import google_request


def request() -> GoogleReportingCatalogRequestV1:
    return GoogleReportingCatalogRequestV1(
        scope=google_request().aggregate.scope,
        actor_id="a" * 32,
        original_session_digest="b" * 64,
        started_at=NOW,
    )


def action(number: int = 1) -> dict[str, Any]:
    return {
        "conversionAction": {
            "resourceName": f"customers/1234567890/conversionActions/{number}",
            "ownerCustomer": "customers/1234567890",
            "name": "Same display name",
            "status": "ENABLED",
            "category": "CONTACT",
            "type": "UPLOAD_CLICKS",
        }
    }


def reader(
    handle: Any,
    *,
    clock: Any = lambda: NOW,
    validate: Any = lambda r: None,
    context_digest: str | None = None,
) -> GoogleReportingCatalogHTTP:
    def context(req: GoogleReportingCatalogRequestV1) -> GoogleReportingCatalogContext:
        return GoogleReportingCatalogContext(
            request_digest=context_digest or req.digest(),
            expires_at=NOW + timedelta(minutes=5),
            access_token=SecretStr("fixture-access"),
            developer_token=SecretStr("fixture-developer"),
        )

    return GoogleReportingCatalogHTTP(
        context, validate, transport=httpx.MockTransport(handle), clock=clock
    )


def test_complete_unfiltered_both_families_and_stable_session_bound_identifiers() -> None:
    calls = []

    def handle(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        assert req.url.path == "/v24/customers/1234567890/googleAds:search"
        body = json.loads(req.content)
        if "FROM customer" in body["query"]:
            return httpx.Response(200, json=response(body["query"]))
        assert "PURCHASE" not in body["query"] and "WEBPAGE" not in body["query"]
        return httpx.Response(
            200,
            json={
                "results": [action(2 if body["pageToken"] else 1)],
                "nextPageToken": "" if body["pageToken"] else "next",
            },
        )

    result = reader(handle)(request())
    assert result.page_count == 2 and len(result.options) == 4 and len(calls) == 3
    assert result.expires_at == NOW + timedelta(seconds=60)
    assert len({x.identifier(request()) for x in result.options}) == 4
    option = result.options[0]
    assert option.identifier(request()) == option.identifier(
        request().model_copy(update={"started_at": NOW + timedelta(seconds=1)})
    )
    assert option.identifier(request()) != option.identifier(
        request().model_copy(update={"original_session_digest": "c" * 64})
    )
    assert option.identifier(request()) != option.model_copy(
        update={"label": "Renamed"}
    ).identifier(request())
    assert (
        result.digest()
        == GoogleReportingCatalogV1.model_validate_json(result.model_dump_json()).digest()
    )


@pytest.mark.parametrize(
    "kind",
    [
        "owner",
        "owner_format",
        "disabled",
        "label",
        "duplicate",
        "cursor",
        "provider",
        "metadata",
        "large",
        "profile",
    ],
)
def test_invalid_or_incomplete_catalog_rejects(kind: str) -> None:
    def handle(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        if "FROM customer" in body["query"]:
            data = response(body["query"])
            if kind == "metadata":
                data["results"][0]["customer"]["currencyCode"] = "EUR"
        else:
            row = action()
            if kind == "owner":
                row["conversionAction"]["ownerCustomer"] = "customers/9999999999"
            if kind == "owner_format":
                row["conversionAction"]["ownerCustomer"] = "1234567890"
            if kind == "disabled":
                row["conversionAction"]["status"] = "REMOVED"
            if kind == "label":
                row["conversionAction"]["name"] = "secret\nvalue"
            data = {"results": [row]}
            if kind == "duplicate":
                data["results"] *= 2
            if kind == "cursor":
                data["nextPageToken"] = "repeat"
            if kind == "provider":
                data["error"] = "private provider details"
            if kind == "large":
                return httpx.Response(200, content=b" " * 8_000_001)
            if kind == "profile":
                data["results"] = [action(i) for i in range(500)]
        return httpx.Response(200, json=data)

    with pytest.raises(
        GoogleReportingCatalogUnavailable, match="^google_reporting_catalog_unavailable$"
    ):
        reader(handle)(request())


@pytest.mark.parametrize("status", [301, 401, 403, 429, 500])
def test_status_errors_sanitized(status: int) -> None:
    with pytest.raises(
        GoogleReportingCatalogUnavailable, match="^google_reporting_catalog_unavailable$"
    ):
        reader(lambda req: httpx.Response(status, json={"secret": "provider-body"}))(request())


def test_empty_catalog_and_context_binding() -> None:
    def handle(req: httpx.Request) -> httpx.Response:
        query = json.loads(req.content)["query"]
        return httpx.Response(200, json=response(query) if "FROM customer" in query else {})

    assert reader(handle)(request()).options == ()
    with pytest.raises(GoogleReportingCatalogUnavailable):
        reader(lambda req: pytest.fail("must not read"), context_digest="d" * 64)(request())


@pytest.mark.parametrize("at", [2, 6, 7])
def test_authorization_delay_or_finalization_expiry(at: int) -> None:
    clock = [NOW]
    checks = []

    def validate(req: Any) -> None:
        checks.append(1)
        if len(checks) == at:
            clock[0] += timedelta(seconds=61)

    def handle(req: httpx.Request) -> httpx.Response:
        query = json.loads(req.content)["query"]
        return httpx.Response(
            200, json=response(query) if "FROM customer" in query else {"results": [action()]}
        )

    with pytest.raises(GoogleReportingCatalogUnavailable):
        reader(handle, clock=lambda: clock[0], validate=validate)(request())


def test_copied_invalid_option_is_revalidated() -> None:
    def handle(req: httpx.Request) -> httpx.Response:
        query = json.loads(req.content)["query"]
        return httpx.Response(
            200, json=response(query) if "FROM customer" in query else {"results": [action()]}
        )

    result = reader(handle)(request())
    with pytest.raises(ValidationError):
        GoogleReportingCatalogV1.model_validate(
            result.model_copy(update={"options": result.options[:1]})
        )


def test_trickling_body_closes_at_deadline_and_private_flag_restores() -> None:
    from collections.abc import Iterator

    from app.executors.social_http import _private_http

    clock = [NOW]
    closed = []
    chunks = []

    class Stream(httpx.SyncByteStream):
        def __iter__(self) -> Iterator[bytes]:
            assert _private_http.get()
            chunks.append(1)
            yield b"{"
            clock[0] += timedelta(seconds=61)
            chunks.append(2)
            yield b" "
            chunks.append(3)
            yield b"}"

        def close(self) -> None:
            closed.append(True)

    before = _private_http.get()
    with pytest.raises(GoogleReportingCatalogUnavailable):
        reader(lambda req: httpx.Response(200, stream=Stream()), clock=lambda: clock[0])(request())
    assert chunks == [1, 2] and closed and _private_http.get() == before


def test_required_developer_context_secret_exclusion() -> None:
    context = GoogleReportingCatalogContext(
        request_digest=request().digest(),
        expires_at=NOW + timedelta(seconds=30),
        access_token=SecretStr("private-access"),
        developer_token=SecretStr(""),
    )
    assert "private-access" not in context.model_dump_json() + repr(context)
    adapter = GoogleReportingCatalogHTTP(
        lambda req: context,
        lambda req: None,
        transport=httpx.MockTransport(lambda req: pytest.fail("must not read")),
        clock=lambda: NOW,
    )
    with pytest.raises(GoogleReportingCatalogUnavailable):
        adapter(request())
