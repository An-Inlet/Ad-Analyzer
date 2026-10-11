import json
from datetime import UTC, timedelta
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
    assert result.digest() == GoogleReportingCatalogV1.model_validate(result).digest()


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


def test_session_binding_excluded_from_request_and_catalog_serialization() -> None:
    req = request()
    catalog = GoogleReportingCatalogV1(
        request=req,
        request_digest=req.digest(),
        observed_at=NOW,
        expires_at=NOW + timedelta(seconds=30),
        page_count=1,
        options=(),
    )
    for value in (req, catalog):
        assert req.original_session_digest not in value.model_dump_json() + repr(value)
        assert "original_session_digest" not in value.model_dump_json()
        with pytest.raises(ValidationError):
            type(value).model_validate_json(value.model_dump_json())
    changed = req.model_copy(update={"original_session_digest": "c" * 64})
    assert changed.digest() != req.digest()
    assert GoogleReportingCatalogRequestV1.model_validate(req).digest() == req.digest()
    with pytest.raises(ValidationError):
        req.model_copy(update={"original_session_digest": "invalid"}).digest()


def test_equivalent_offsets_share_commitment_and_dst_fold_chronology_is_real() -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    zone = ZoneInfo("America/New_York")
    started = datetime(2026, 11, 1, 1, 59, 50, tzinfo=zone, fold=0)
    observed = datetime(2026, 11, 1, 1, 0, 10, tzinfo=zone, fold=1)
    expires = datetime(2026, 11, 1, 1, 0, 30, tzinfo=zone, fold=1)
    req = GoogleReportingCatalogRequestV1.model_validate(
        request().model_copy(update={"started_at": started})
    )
    utc_req = GoogleReportingCatalogRequestV1.model_validate(
        req.model_copy(update={"started_at": started.astimezone(UTC)})
    )
    assert req.digest() == utc_req.digest() and req.started_at.tzinfo is UTC
    catalog = GoogleReportingCatalogV1(
        request=req,
        request_digest=req.digest(),
        observed_at=observed,
        expires_at=expires,
        page_count=1,
        options=(),
    )
    assert catalog.observed_at.tzinfo is UTC and catalog.expires_at.tzinfo is UTC
    assert catalog.expires_at - req.started_at == timedelta(seconds=40)
    # Same wall time in different folds is one hour apart, not equal/current.
    with pytest.raises(ValidationError):
        GoogleReportingCatalogV1.model_validate(
            catalog.model_copy(
                update={"observed_at": expires.replace(fold=0), "expires_at": observed}
            )
        )
    with pytest.raises(ValidationError):
        GoogleReportingCatalogV1.model_validate(
            catalog.model_copy(update={"expires_at": observed.replace(minute=10)})
        )


@pytest.mark.parametrize("bad", [1793512800, "1793512800", "2026-11-01", "2026-11-01T01:00:00"])
def test_strict_instants_reject_coercion_and_copied_values(bad: Any) -> None:
    with pytest.raises(ValidationError):
        GoogleReportingCatalogRequestV1.model_validate(
            request().model_copy(update={"started_at": bad})
        )
    ctx = GoogleReportingCatalogContext(
        request_digest=request().digest(),
        expires_at=NOW,
        access_token=SecretStr("fixture"),
        developer_token=SecretStr("fixture"),
    )
    with pytest.raises(ValidationError):
        GoogleReportingCatalogContext.model_validate(ctx.model_copy(update={"expires_at": bad}))
    catalog = GoogleReportingCatalogV1(
        request=request(),
        request_digest=request().digest(),
        observed_at=NOW,
        expires_at=NOW + timedelta(seconds=30),
        page_count=1,
        options=(),
    )
    with pytest.raises(ValidationError):
        GoogleReportingCatalogV1.model_validate(catalog.model_copy(update={"observed_at": bad}))


def test_http_deadline_across_fold_uses_elapsed_utc_and_rejects_naive_clock() -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    zone = ZoneInfo("America/New_York")
    started = datetime(2026, 11, 1, 1, 59, 50, tzinfo=zone, fold=0)
    clock = [started]
    req = GoogleReportingCatalogRequestV1.model_validate(
        request().model_copy(update={"started_at": started})
    )
    ctx = GoogleReportingCatalogContext(
        request_digest=req.digest(),
        expires_at=datetime(2026, 11, 1, 1, 0, 30, tzinfo=zone, fold=1),
        access_token=SecretStr("fixture"),
        developer_token=SecretStr("fixture"),
    )

    def handle(raw: httpx.Request) -> httpx.Response:
        clock[0] = datetime(2026, 11, 1, 1, 0, 10, tzinfo=zone, fold=1)
        query = json.loads(raw.content)["query"]
        return httpx.Response(200, json=response(query) if "FROM customer" in query else {})

    adapter = GoogleReportingCatalogHTTP(
        lambda r: ctx, lambda r: None, transport=httpx.MockTransport(handle), clock=lambda: clock[0]
    )
    result = adapter(req)
    assert result.expires_at - result.observed_at == timedelta(seconds=20)
    clock[0] = started.replace(tzinfo=None)
    with pytest.raises(GoogleReportingCatalogUnavailable):
        adapter(req)


@pytest.mark.parametrize("field", ["resource_name", "owner_customer_id"])
def test_copied_native_identifiers_require_strict_strings(field: str) -> None:
    from app.google_connections.selected_catalog import GoogleReportingOptionV1
    from app.google_connections.selected_presence import query_profile_digest

    option = GoogleReportingOptionV1(
        resource_name="customers/1234567890/conversionActions/1",
        owner_customer_id="1234567890",
        label="Observed event",
        status="ENABLED",
        category="CONTACT",
        action_type="UPLOAD_CLICKS",
        metric_family="conversions",
        query_profile_digest=query_profile_digest("conversions"),
    )
    bad = option.model_copy(update={field: getattr(option, field).encode()})
    with pytest.raises(ValidationError):
        bad.identifier(request())
