"""Actual GAQL/HTTP discovery with no provider network or customer data."""

import copy
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from app.collectors.google_catalog import (
    GoogleCatalogContext,
    GoogleCatalogHTTP,
    GoogleCatalogUnavailable,
)
from app.publication.customer_catalog import GoogleCatalogRequest
from pydantic import SecretStr

NOW = datetime(2026, 10, 6, tzinfo=UTC)
CUSTOMER = "1234567890"
GOAL = f"customers/{CUSTOMER}/customConversionGoals/1"
ACTION = f"customers/{CUSTOMER}/conversionActions/2"


def request() -> GoogleCatalogRequest:
    return GoogleCatalogRequest.model_validate(
        {
            "account": {
                "workspace_id": 1,
                "account": {"platform": "google_ads", "account_id": 2, "connection_id": 3},
                "external_advertiser_id": CUSTOMER,
                "connection_version": "google:1:1",
            },
            "draft_id": "a" * 32,
            "draft_revision": 1,
            "source_digest": "b" * 64,
            "countries": ["US"],
            "languages": ["en"],
        }
    )


def context(req: GoogleCatalogRequest, now: datetime) -> GoogleCatalogContext:
    return GoogleCatalogContext(
        account=req.account,
        request_digest=req.digest(),
        expires_at=now + timedelta(minutes=2),
        access_token=SecretStr("test-secret"),
    )


def rows() -> dict[str, list[dict[str, Any]]]:
    return {
        "customer": [
            {"id": CUSTOMER, "resourceName": f"customers/{CUSTOMER}", "status": "ENABLED"}
        ],
        "customConversionGoal": [
            {
                "resourceName": GOAL,
                "name": "Store Purchases",
                "status": "ENABLED",
                "conversionActions": [ACTION],
            }
        ],
        "conversionAction": [
            {
                "resourceName": ACTION,
                "ownerCustomer": f"customers/{CUSTOMER}",
                "status": "ENABLED",
                "category": "PURCHASE",
                "type": "WEBPAGE",
            }
        ],
        "geoTargetConstant": [
            {
                "resourceName": "geoTargetConstants/2840",
                "countryCode": "US",
                "targetType": "Country",
                "status": "ENABLED",
            }
        ],
        "languageConstant": [
            {"resourceName": "languageConstants/1000", "code": "en", "targetable": True}
        ],
    }


def key_for(query: str) -> str:
    table = query.split(" FROM ")[1].split(" ")[0]
    return table.split("_")[0] + "".join(x.title() for x in table.split("_")[1:])


def reader(
    data: dict[str, list[dict[str, Any]]] | None = None,
) -> tuple[GoogleCatalogHTTP, list[httpx.Request]]:
    data = rows() if data is None else data
    calls: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        key = key_for(json.loads(req.content)["query"])
        return httpx.Response(200, json={"results": [{key: r} for r in data[key]]})

    return GoogleCatalogHTTP(
        context, transport=httpx.MockTransport(handler), clock=lambda: NOW
    ), calls


def test_actual_wire_owned_names_and_opaque_stable_options(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    adapter, calls = reader()
    req = request()
    catalog = adapter(req, NOW)
    assert catalog.request == req
    assert catalog.expires_at == NOW + timedelta(minutes=2)
    option = catalog.options[0]
    assert option.label == "Store Purchases"
    assert option.conversion_actions == [ACTION]
    assert option.country_targets == {"US": "geoTargetConstants/2840"}
    assert option.language_targets == {"en": "languageConstants/1000"}
    assert len(option.identifier(req)) == 64
    assert option.identifier(req) == adapter(req, NOW).options[0].identifier(req)
    assert option.identifier(req) != option.identifier(req.model_copy(update={"draft_revision": 2}))
    assert len(calls) == 10
    assert all(
        r.method == "POST"
        and str(r.url)
        == f"https://googleads.googleapis.com/v25/customers/{CUSTOMER}/googleAds:search"
        for r in calls
    )
    assert all(
        r.headers["authorization"] == "Bearer test-secret"
        and r.headers["accept-encoding"] == "identity"
        for r in calls
    )
    assert all("developer-token" not in r.headers for r in calls)
    assert all("mutate" not in str(r.url) for r in calls)
    assert "test-secret" not in caplog.text and CUSTOMER not in caplog.text
    assert "test-secret" not in context(req, NOW).model_dump_json()
    assert "test-secret" not in repr(context(req, NOW))


@pytest.mark.parametrize(
    "field,value",
    [
        ("category", "LEAD"),
        ("type", "GOOGLE_ANALYTICS_4_PURCHASE"),
        ("status", "REMOVED"),
        ("ownerCustomer", "customers/9999999999"),
        ("ownerCustomer", None),
    ],
)
def test_unsupported_or_foreign_actions_never_become_choices(field: str, value: Any) -> None:
    data = rows()
    data["conversionAction"][0][field] = value
    adapter, _ = reader(data)
    result = adapter(request(), NOW)
    assert result.options == []
    assert "catalog_unsupported_conversion_goal" in result.unavailable_reasons


@pytest.mark.parametrize(
    "key,field,value",
    [
        ("customer", "id", "9999999999"),
        ("customer", "manager", True),
        ("customConversionGoal", "resourceName", "customers/9999999999/customConversionGoals/1"),
        ("customConversionGoal", "name", "bad\nname"),
        ("customConversionGoal", "name", "customers/1234567890/customConversionGoals/1"),
        ("geoTargetConstant", "targetType", "City"),
        ("geoTargetConstant", "status", "REMOVAL_PLANNED"),
        ("geoTargetConstant", "countryCode", "CA"),
        ("geoTargetConstant", "resourceName", "https://evil.invalid"),
        ("languageConstant", "targetable", False),
        ("languageConstant", "code", "fr"),
    ],
)
def test_bad_native_identity_targets_and_names_fail_closed(
    key: str, field: str, value: Any
) -> None:
    data = rows()
    data[key][0][field] = value
    adapter, _ = reader(data)
    with pytest.raises(GoogleCatalogUnavailable):
        adapter(request(), NOW)


@pytest.mark.parametrize(
    "key",
    [
        "customer",
        "customConversionGoal",
        "conversionAction",
        "geoTargetConstant",
        "languageConstant",
    ],
)
def test_duplicate_rows_rejected(key: str) -> None:
    data = rows()
    data[key].append(copy.deepcopy(data[key][0]))
    adapter, _ = reader(data)
    with pytest.raises(GoogleCatalogUnavailable):
        adapter(request(), NOW)


def test_same_names_do_not_require_numeric_ids_for_disambiguation() -> None:
    data = rows()
    other = dict(
        data["customConversionGoal"][0],
        resourceName=f"customers/{CUSTOMER}/customConversionGoals/3",
    )
    data["customConversionGoal"].append(other)
    adapter, _ = reader(data)
    with pytest.raises(GoogleCatalogUnavailable, match="catalog_ambiguous_names"):
        adapter(request(), NOW)


def test_pagination_complete_then_sorted_stable_options() -> None:
    calls = []
    data = rows()

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        key = key_for(body["query"])
        calls.append(body)
        if key == "customConversionGoal" and "pageToken" not in body:
            return httpx.Response(200, json={"nextPageToken": "opaque"})
        return httpx.Response(200, json={"results": [{key: r} for r in data[key]]})

    adapter = GoogleCatalogHTTP(context, transport=httpx.MockTransport(handler), clock=lambda: NOW)
    assert len(adapter(request(), NOW).options) == 1
    assert len(calls) == 6
    assert calls[2]["pageToken"] == "opaque"


@pytest.mark.parametrize(
    "kind",
    ["cycle", "oversize", "too_many", "error", "redirect", "malformed", "compressed", "timeout"],
)
def test_protocol_bounds_and_sanitized_errors(kind: str, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        if kind == "timeout":
            raise httpx.ReadTimeout("test-secret raw sensitive provider body")
        if kind == "cycle":
            return httpx.Response(200, json={"nextPageToken": "same"})
        if kind == "oversize":
            return httpx.Response(200, content=b"x" * 1_000_001)
        if kind == "too_many":
            return httpx.Response(200, json={"results": [{"customer": {}}] * 201})
        if kind == "error":
            return httpx.Response(200, json={"error": "test-secret"})
        if kind == "redirect":
            return httpx.Response(302, headers={"location": "https://evil.invalid/test-secret"})
        if kind == "compressed":
            return httpx.Response(200, headers={"content-encoding": "identity, identity"})
        return httpx.Response(200, content=b"test-secret invalid json")

    adapter = GoogleCatalogHTTP(context, transport=httpx.MockTransport(handler), clock=lambda: NOW)
    with pytest.raises(GoogleCatalogUnavailable) as error:
        adapter(request(), NOW)
    assert "test-secret" not in str(error.value) and "test-secret" not in caplog.text
    assert len(calls) <= 2


@pytest.mark.parametrize("change", ["scope", "draft", "expired"])
def test_context_binding_prevents_any_io(change: str) -> None:
    def wrong(req: GoogleCatalogRequest, now: datetime) -> GoogleCatalogContext:
        result = context(req, now)
        if change == "scope":
            result.account = req.account.model_copy(update={"connection_version": "google:1:2"})
        elif change == "draft":
            result.request_digest = "c" * 64
        else:
            result.expires_at = now
        return result

    calls: list[httpx.Request] = []

    def forbidden(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        raise AssertionError("unexpected IO")

    adapter = GoogleCatalogHTTP(wrong, transport=httpx.MockTransport(forbidden), clock=lambda: NOW)
    with pytest.raises(GoogleCatalogUnavailable):
        adapter(request(), NOW)
    assert calls == []


def test_expiry_during_last_io_cannot_return_catalog() -> None:
    data = rows()
    clock = [NOW]

    def handler(req: httpx.Request) -> httpx.Response:
        key = key_for(json.loads(req.content)["query"])
        if key == "languageConstant":
            clock[0] = NOW + timedelta(minutes=3)
        return httpx.Response(200, json={"results": [{key: r} for r in data[key]]})

    adapter = GoogleCatalogHTTP(
        context, transport=httpx.MockTransport(handler), clock=lambda: clock[0]
    )
    with pytest.raises(GoogleCatalogUnavailable, match="catalog_expired"):
        adapter(request(), NOW)


def test_query_input_rejected_before_context_resolution() -> None:
    adapter, calls = reader()
    with pytest.raises(GoogleCatalogUnavailable, match="catalog_request_invalid"):
        adapter(request().model_copy(update={"countries": ["US' OR 1=1"]}), NOW)
    assert calls == []


def test_catalog_never_truncates_51_goals() -> None:
    data = rows()
    template = data["customConversionGoal"][0]
    data["customConversionGoal"] = [
        dict(
            template,
            resourceName=f"customers/{CUSTOMER}/customConversionGoals/{i}",
            name=f"Purchase Goal {i}",
        )
        for i in range(51)
    ]
    adapter, _ = reader(data)
    with pytest.raises(GoogleCatalogUnavailable, match="catalog_inventory_bounds"):
        adapter(request(), NOW)


def test_optional_legacy_headers_are_server_only() -> None:
    adapter, calls = reader()

    def configured(req: GoogleCatalogRequest, now: datetime) -> GoogleCatalogContext:
        value = context(req, now)
        value.developer_token = SecretStr("legacy-test")
        value.login_customer_id = "2222222222"
        return value

    adapter.context_reader = configured
    adapter(request(), NOW)
    assert all(
        r.headers["developer-token"] == "legacy-test"
        and r.headers["login-customer-id"] == "2222222222"
        for r in calls
    )


def test_complete_goal_action_set_is_required() -> None:
    data = rows()
    data["customConversionGoal"][0]["conversionActions"].append(
        f"customers/{CUSTOMER}/conversionActions/999"
    )
    adapter, _ = reader(data)
    assert adapter(request(), NOW).options == []
