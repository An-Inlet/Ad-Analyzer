"""Injected selected-action reads; no default factory, grants or advertising writes."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Annotated, Any, Literal

import httpx
from pydantic import AwareDatetime, Field, SecretStr

from app.campaign_performance.presence_contracts import Digest, Frozen
from app.campaign_performance.raw_cells import exact_json
from app.campaign_performance.selected_contracts import (
    SelectedCaptureRequestV1,
    capture_request_digest,
)
from app.executors.social_http import _private_http
from app.google_connections.selected_presence import (
    PRODUCER,
    GoogleSelectedPageV1,
    parse_selected_page,
    query_profile_digest,
)


class SelectedGoogleContext(Frozen):
    request_digest: Digest
    expires_at: AwareDatetime
    access_token: SecretStr = Field(exclude=True, repr=False)
    developer_token: SecretStr = Field(exclude=True, repr=False)
    login_customer_id: Annotated[str, Field(strict=True, pattern=r"^[0-9]{10}$")] | None = Field(
        default=None, exclude=True, repr=False
    )


ContextReader = Callable[[SelectedCaptureRequestV1], SelectedGoogleContext]
Revalidate = Callable[[SelectedCaptureRequestV1], None]


class GoogleSelectedReadUnavailable(RuntimeError):
    """Fixed safe failure only; never provider error bodies, headers or credentials."""


class GoogleSelectedHTTPRead:
    def __init__(
        self,
        context_reader: ContextReader,
        revalidate: Revalidate,
        *,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.context_reader = context_reader
        self.revalidate = revalidate
        self.transport = transport
        self.clock = clock

    def __call__(
        self,
        request: SelectedCaptureRequestV1,
        campaign_mapping: dict[str, int],
        *,
        requested_cursor: str = "",
    ) -> GoogleSelectedPageV1:
        private = _private_http.set(True)
        try:
            req = SelectedCaptureRequestV1.model_validate(request)
            mapping = dict(campaign_mapping)
            # Validate profile/mapping/cursor before any token resolution or IO.
            parse_selected_page(b"{}", req, mapping, requested_cursor=requested_cursor)
            selection = req.selection
            family: Literal["conversions", "all_conversions"] = (
                "conversions" if selection.metric_family == "conversions" else "all_conversions"
            )
            if (
                req.producer_contract != PRODUCER
                or req.query_profile_digest != query_profile_digest(family)
            ):
                raise ValueError("unsupported query profile")
            self.revalidate(req)
            context = SelectedGoogleContext.model_validate(self.context_reader(req))
            if context.request_digest != capture_request_digest(req) or not (
                context.access_token.get_secret_value()
                and context.developer_token.get_secret_value()
            ):
                raise ValueError("read context mismatch")
            initial = self.clock()
            if initial.tzinfo is None:
                raise ValueError("aware clock required")
            started = initial.astimezone(UTC)
            expires = min(started + timedelta(seconds=60), context.expires_at.astimezone(UTC))
            deadline = monotonic() + 60

            def time_check() -> None:
                now = self.clock()
                if now.tzinfo is None or not req.started_at <= now.astimezone(UTC) < expires:
                    raise ValueError("read context expired")
                if monotonic() >= deadline:
                    raise ValueError("read deadline exceeded")

            def check() -> None:
                time_check()
                self.revalidate(req)
                # Authorization may block. Never use its pre-call clock sample
                # to admit another query or return a now-expired result.
                time_check()

            advertiser = req.aggregate.scope.native_account_id
            headers = {
                "Authorization": "Bearer " + context.access_token.get_secret_value(),
                "developer-token": context.developer_token.get_secret_value(),
                "Accept-Encoding": "identity",
            }
            if context.login_customer_id:
                headers["login-customer-id"] = context.login_customer_id
            url = f"https://googleads.googleapis.com/v24/customers/{advertiser}/googleAds:search"
            with httpx.Client(
                transport=self.transport,
                timeout=httpx.Timeout(12, connect=5),
                follow_redirects=False,
                trust_env=False,
            ) as client:

                def read(query: str, *, cursor: str = "", cap: int = 200_000) -> bytes:
                    check()
                    with client.stream(
                        "POST", url, headers=headers, json={"query": query, "pageToken": cursor}
                    ) as response:
                        if response.status_code != 200:
                            raise ValueError("provider read unavailable")
                        raw = bytearray()
                        for chunk in response.iter_bytes():
                            # Read timeout applies per transport read. This check
                            # bounds a trickling body; a blocked read can still
                            # consume up to the configured transport timeout.
                            time_check()
                            raw.extend(chunk)
                            if len(raw) > cap:
                                raise ValueError("response byte bound")
                    check()
                    return bytes(raw)

                def metadata(query: str, key: str) -> dict[str, Any]:
                    value = exact_json(read(query), limit=200_000)
                    rows = value.get("results")
                    if (
                        "error" in value
                        or value.get("nextPageToken", "") != ""
                        or type(rows) is not list
                        or len(rows) != 1
                        or type(rows[0]) is not dict
                        or type(rows[0].get(key)) is not dict
                    ):
                        raise ValueError("metadata unavailable")
                    result: dict[str, Any] = rows[0][key]
                    return result

                account = metadata(
                    "SELECT customer.id, customer.resource_name, customer.currency_code, "
                    "customer.time_zone FROM customer",
                    "customer",
                )
                if account != {
                    "id": advertiser,
                    "resourceName": f"customers/{advertiser}",
                    "currencyCode": req.aggregate.scope.currency,
                    "timeZone": req.aggregate.scope.time_zone,
                }:
                    raise ValueError("account metadata mismatch")
                event = selection.native_event_id
                action = metadata(
                    "SELECT conversion_action.resource_name, conversion_action.owner_customer "
                    f"FROM conversion_action WHERE conversion_action.resource_name = '{event}'",
                    "conversionAction",
                )
                if action != {"resourceName": event, "ownerCustomer": f"customers/{advertiser}"}:
                    raise ValueError("event ownership mismatch")
                value_metric = (
                    "conversions_value" if family == "conversions" else "all_conversions_value"
                )
                query = (
                    "SELECT campaign.id, campaign.resource_name, segments.date, "
                    f"segments.conversion_action, metrics.{family}, metrics.{value_metric} "
                    f"FROM campaign WHERE segments.conversion_action = '{event}' "
                    f"AND segments.date BETWEEN '{req.requested_starts_on.isoformat()}' "
                    f"AND '{req.requested_ends_on.isoformat()}'"
                )
                result = parse_selected_page(
                    read(query, cursor=requested_cursor, cap=8_000_000),
                    req,
                    mapping,
                    requested_cursor=requested_cursor,
                )
                check()
                return result
        except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
            raise GoogleSelectedReadUnavailable("google_selected_read_unavailable") from None
        finally:
            _private_http.reset(private)
