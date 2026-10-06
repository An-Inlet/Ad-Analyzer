"""Read-only Google v25 named configuration discovery, never execution authority.

Explicitly injected by a server composition root; no default factory or live setup.
Caller rechecks session/role/account generation/draft after this external IO.
"""

import json
import re
import unicodedata
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Any

import httpx
from pydantic import AwareDatetime, Field, SecretStr

from app.executors.social_http import _private_http
from app.goals.schemas import StrictModel
from app.publication.customer_catalog import (
    GoogleCatalog,
    GoogleCatalogOption,
    GoogleCatalogRequest,
)
from app.publication.execution_contracts import ExecutionAccount
from app.publication.provider_contracts import Digest


class GoogleCatalogUnavailable(RuntimeError):
    """Only fixed reason codes; no raw provider message or customer identifiers."""


class GoogleCatalogContext(StrictModel):
    account: ExecutionAccount
    request_digest: Digest
    expires_at: AwareDatetime
    access_token: SecretStr = Field(exclude=True, repr=False)
    developer_token: SecretStr | None = Field(default=None, exclude=True, repr=False)
    login_customer_id: str | None = Field(default=None, pattern=r"^[0-9]{10}$", exclude=True)


ContextReader = Callable[[GoogleCatalogRequest, datetime], GoogleCatalogContext]


def _resource(value: Any, prefix: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(re.escape(prefix) + r"[0-9]{1,20}", value):
        raise GoogleCatalogUnavailable("catalog_resource_invalid")
    return value


def _label(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value.strip()) <= 160
        or any(unicodedata.category(c).startswith("C") for c in value)
        or re.search(r"customers/[0-9]+/", value)
    ):
        raise GoogleCatalogUnavailable("catalog_name_unavailable")
    return value.strip()


class GoogleCatalogHTTP:
    def __init__(
        self,
        context_reader: ContextReader,
        *,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.context_reader = context_reader
        self.transport = transport
        self.clock = clock

    def __call__(self, request: GoogleCatalogRequest, now: datetime, /) -> GoogleCatalog:
        request = GoogleCatalogRequest.model_validate(request.model_dump())
        if (
            request.account.account.platform != "google_ads"
            or not re.fullmatch(r"[0-9]{10}", request.account.external_advertiser_id)
            or len(set(request.countries)) != len(request.countries)
            or len(set(request.languages)) != len(request.languages)
            or any(not re.fullmatch(r"[A-Z]{2}", c) for c in request.countries)
            or any(
                not re.fullmatch(r"[a-z]{2,3}(?:[-_][A-Za-z]{2,4})?", c) for c in request.languages
            )
        ):
            raise GoogleCatalogUnavailable("catalog_request_invalid")
        context = self.context_reader(request, now)
        # Explicit fields avoid revalidating a serialization with excluded credentials.
        if (
            context.account != request.account
            or context.request_digest != request.digest()
            or not context.access_token.get_secret_value()
        ):
            raise GoogleCatalogUnavailable("catalog_context_invalid")
        expires = min(now + timedelta(minutes=5), context.expires_at)
        deadline = monotonic() + 60

        def check() -> None:
            if not now <= self.clock() < expires or monotonic() >= deadline:
                raise GoogleCatalogUnavailable("catalog_expired")

        check()
        headers = {
            "Authorization": "Bearer " + context.access_token.get_secret_value(),
            "Accept-Encoding": "identity",
        }
        if context.developer_token:
            headers["developer-token"] = context.developer_token.get_secret_value()
        if context.login_customer_id:
            headers["login-customer-id"] = context.login_customer_id
        customer = request.account.external_advertiser_id
        url = f"https://googleads.googleapis.com/v25/customers/{customer}/googleAds:search"
        private = _private_http.set(True)
        try:
            with httpx.Client(
                transport=self.transport,
                timeout=httpx.Timeout(12, connect=5),
                follow_redirects=False,
                trust_env=False,
            ) as client:

                def search(query: str, key: str, limit: int = 200) -> list[dict[str, Any]]:
                    rows: list[dict[str, Any]] = []
                    seen: set[str] = set()
                    body: dict[str, Any] = {"query": query}
                    for _ in range(10):
                        check()
                        with client.stream("POST", url, headers=headers, json=body) as response:
                            if (
                                response.status_code != 200
                                or response.headers.get("Content-Encoding", "identity")
                                != "identity"
                            ):
                                raise GoogleCatalogUnavailable("catalog_provider_unavailable")
                            raw = bytearray()
                            for chunk in response.iter_bytes():
                                check()
                                raw.extend(chunk)
                                if len(raw) > 1_000_000:
                                    raise GoogleCatalogUnavailable("catalog_response_bounds")
                        check()
                        data = json.loads(raw)
                        if (
                            not isinstance(data, dict)
                            or "error" in data
                            or "partialFailureError" in data
                        ):
                            raise GoogleCatalogUnavailable("catalog_response_invalid")
                        page = data.get("results", [])
                        if not isinstance(page, list) or any(
                            not isinstance(r, dict) or not isinstance(r.get(key), dict)
                            for r in page
                        ):
                            raise GoogleCatalogUnavailable("catalog_response_invalid")
                        rows.extend(r[key] for r in page)
                        if len(rows) > limit:
                            raise GoogleCatalogUnavailable("catalog_inventory_bounds")
                        token = data.get("nextPageToken")
                        if token is None or token == "":
                            return rows
                        if not isinstance(token, str) or len(token) > 4096 or token in seen:
                            raise GoogleCatalogUnavailable("catalog_cursor_invalid")
                        seen.add(token)
                        body["pageToken"] = token
                    raise GoogleCatalogUnavailable("catalog_inventory_bounds")

                accounts = search(
                    "SELECT customer.id, customer.resource_name, customer.status, customer.manager "
                    "FROM customer",
                    "customer",
                    1,
                )
                if len(accounts) != 1 or (
                    str(accounts[0].get("id")) != customer
                    or accounts[0].get("resourceName") != f"customers/{customer}"
                    or accounts[0].get("status") != "ENABLED"
                    or accounts[0].get("manager", False) is not False
                ):
                    raise GoogleCatalogUnavailable("catalog_account_unavailable")
                goals = search(
                    "SELECT custom_conversion_goal.resource_name, custom_conversion_goal.name, "
                    "custom_conversion_goal.status, custom_conversion_goal.conversion_actions "
                    "FROM custom_conversion_goal WHERE custom_conversion_goal.status = 'ENABLED'",
                    "customConversionGoal",
                    50,
                )
                actions = search(
                    "SELECT conversion_action.resource_name, conversion_action.owner_customer, "
                    "conversion_action.status, conversion_action.category, conversion_action.type "
                    "FROM conversion_action WHERE conversion_action.status = 'ENABLED'",
                    "conversionAction",
                )
                owned_actions: set[str] = set()
                all_actions: set[str] = set()
                for action in actions:
                    ref = action.get("resourceName")
                    # Manager-owned/system conversion actions are unsupported, not customer proof.
                    if (
                        not isinstance(ref, str)
                        or not re.fullmatch(
                            r"customers/[0-9]{10}/conversionActions/[0-9]{1,20}", ref
                        )
                        or ref in all_actions
                    ):
                        raise GoogleCatalogUnavailable("catalog_resource_invalid")
                    all_actions.add(ref)
                    if (
                        ref.startswith(f"customers/{customer}/conversionActions/")
                        and action.get("ownerCustomer") == f"customers/{customer}"
                        and action.get("status") == "ENABLED"
                        and action.get("category") == "PURCHASE"
                        and action.get("type") == "WEBPAGE"
                    ):
                        owned_actions.add(ref)

                def targets(codes: list[str], language: bool) -> dict[str, str]:
                    table = "language_constant" if language else "geo_target_constant"
                    key = "languageConstant" if language else "geoTargetConstant"
                    code = "code" if language else "country_code"
                    extra = "targetable" if language else "target_type, geo_target_constant.status"
                    values = ", ".join(f"'{c}'" for c in sorted(codes))
                    rows = search(
                        f"SELECT {table}.resource_name, {table}.{code}, {table}.{extra} "
                        f"FROM {table} WHERE {table}.{code} IN ({values})"
                        + ("" if language else " AND geo_target_constant.target_type = 'Country'"),
                        key,
                    )
                    result: dict[str, str] = {}
                    for row in rows:
                        value = row.get("code" if language else "countryCode")
                        if value not in codes or value in result:
                            raise GoogleCatalogUnavailable("catalog_targets_unavailable")
                        if (language and row.get("targetable") is not True) or (
                            not language
                            and (
                                row.get("status") != "ENABLED" or row.get("targetType") != "Country"
                            )
                        ):
                            raise GoogleCatalogUnavailable("catalog_targets_unavailable")
                        result[value] = _resource(
                            row.get("resourceName"),
                            "languageConstants/" if language else "geoTargetConstants/",
                        )
                    if set(result) != set(codes):
                        raise GoogleCatalogUnavailable("catalog_targets_unavailable")
                    return result

                countries = targets(request.countries, False)
                languages = targets(request.languages, True)
                options: list[GoogleCatalogOption] = []
                goal_refs: set[str] = set()
                labels: set[str] = set()
                reasons: set[str] = set()
                for goal in goals:
                    ref = _resource(
                        goal.get("resourceName"), f"customers/{customer}/customConversionGoals/"
                    )
                    if ref in goal_refs:
                        raise GoogleCatalogUnavailable("catalog_resource_invalid")
                    goal_refs.add(ref)
                    refs = goal.get("conversionActions")
                    if (
                        goal.get("status") != "ENABLED"
                        or not isinstance(refs, list)
                        or not 1 <= len(refs) <= 20
                        or any(not isinstance(r, str) for r in refs)
                        or len(set(refs)) != len(refs)
                        or not set(refs).issubset(owned_actions)
                    ):
                        reasons.add("catalog_unsupported_conversion_goal")
                        continue
                    label = _label(goal.get("name"))
                    if label.casefold() in labels:
                        raise GoogleCatalogUnavailable("catalog_ambiguous_names")
                    labels.add(label.casefold())
                    options.append(
                        GoogleCatalogOption(
                            label=label,
                            custom_conversion_goal=ref,
                            conversion_actions=sorted(refs),
                            country_targets=countries,
                            language_targets=languages,
                        )
                    )
                check()
                if not options:
                    reasons.add("catalog_no_supported_purchase_goal")
                return GoogleCatalog(
                    request=request,
                    observed_at=now,
                    expires_at=expires,
                    options=sorted(options, key=lambda o: o.label.casefold()),
                    unavailable_reasons=sorted(reasons),
                )
        except (httpx.HTTPError, ValueError, TypeError, OSError):
            raise GoogleCatalogUnavailable("catalog_provider_unavailable") from None
        finally:
            _private_http.reset(private)
