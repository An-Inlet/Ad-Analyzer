"""Injected read-only Meta count transport; never follows provider pagination URLs."""

import hashlib
import hmac
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from time import monotonic

import httpx
from pydantic import AwareDatetime, Field, SecretStr

from app.campaign_performance.presence_contracts import Digest, Frozen
from app.campaign_performance.raw_cells import exact_json
from app.campaign_performance.selected_contracts import (
    SelectedCaptureRequestV1,
    capture_request_digest,
)
from app.executors.social_http import _private_http
from app.meta.selected_presence import MetaSelectedPageV1, parse_selected_page, validate_inputs
from app.meta.selected_profile import FIELDS


class SelectedMetaContext(Frozen):
    request_digest: Digest
    expires_at: AwareDatetime
    access_token: SecretStr = Field(exclude=True, repr=False)
    app_secret: SecretStr = Field(exclude=True, repr=False)


class MetaSelectedReadUnavailable(RuntimeError):
    """Fixed public failure; no provider body, query, header or grant disclosure."""


class _BorrowedTransport(httpx.BaseTransport):
    """The injecting caller owns transport lifetime across page clients."""

    def __init__(self, transport: httpx.BaseTransport) -> None:
        self.transport = transport

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return self.transport.handle_request(request)

    def close(self) -> None:
        pass  # Only the injecting caller closes the underlying transport.


class MetaSelectedHTTPRead:
    def __init__(
        self,
        context_reader: Callable[[SelectedCaptureRequestV1], SelectedMetaContext],
        revalidate: Callable[[SelectedCaptureRequestV1], None],
        *,
        transport: httpx.BaseTransport,
        clock: Callable[[], datetime],
    ) -> None:
        self.context_reader, self.revalidate = context_reader, revalidate
        self.transport, self.clock = transport, clock

    def __call__(
        self,
        request: SelectedCaptureRequestV1,
        campaign_mapping: dict[str, int],
        *,
        requested_cursor: str = "",
    ) -> MetaSelectedPageV1:
        private = _private_http.set(True)
        try:
            req = validate_inputs(request, campaign_mapping, requested_cursor)
            mapping = dict(campaign_mapping)
            self.revalidate(req)
            context = SelectedMetaContext.model_validate(self.context_reader(req))
            if context.request_digest != capture_request_digest(req) or not (
                context.access_token.get_secret_value() and context.app_secret.get_secret_value()
            ):
                raise ValueError("context mismatch")
            expires = min(req.started_at + timedelta(seconds=60), context.expires_at)
            deadline = monotonic() + 60

            def time_check() -> None:
                now = self.clock()
                if (
                    type(now) is not datetime
                    or now.tzinfo is None
                    or now.utcoffset() is None
                    or not req.started_at <= now.astimezone(UTC) < expires
                    or monotonic() >= deadline
                ):
                    raise ValueError("context expired")

            def check() -> None:
                time_check()
                self.revalidate(req)
                time_check()

            advertiser = req.aggregate.scope.native_account_id
            base = f"https://graph.facebook.com/v26.0/act_{advertiser}"
            token = context.access_token.get_secret_value()
            proof = hmac.new(
                context.app_secret.get_secret_value().encode(), token.encode(), hashlib.sha256
            ).hexdigest()
            headers = {"Authorization": "Bearer " + token, "Accept-Encoding": "identity"}
            with httpx.Client(
                transport=_BorrowedTransport(self.transport),
                timeout=httpx.Timeout(12, connect=5),
                follow_redirects=False,
                trust_env=False,
            ) as client:

                def read(edge: str, params: dict[str, str], cap: int) -> bytes:
                    check()
                    with client.stream(
                        "GET",
                        base + edge,
                        headers=headers,
                        params={**params, "appsecret_proof": proof},
                    ) as response:
                        if response.status_code != 200:
                            raise ValueError("report unavailable")
                        raw = bytearray()
                        for chunk in response.iter_bytes():
                            time_check()
                            raw.extend(chunk)
                            if len(raw) > cap:
                                raise ValueError("response capacity exceeded")
                    check()
                    return bytes(raw)

                metadata = exact_json(
                    read("", {"fields": "account_id,currency,timezone_name"}, 200_000),
                    limit=200_000,
                )
                if (
                    set(metadata) - {"id", "account_id", "currency", "timezone_name"}
                    or metadata.get("account_id") != advertiser
                    or metadata.get("id", "act_" + advertiser) != "act_" + advertiser
                    or metadata.get("currency") != req.aggregate.scope.currency
                    or metadata.get("timezone_name") != req.aggregate.scope.time_zone
                ):
                    raise ValueError("account metadata mismatch")
                params = {
                    "fields": FIELDS,
                    "level": "campaign",
                    "time_increment": "1",
                    "limit": "100",
                    "action_breakdowns": '["action_type"]',
                    "time_range": json.dumps(
                        {
                            "since": req.requested_starts_on.isoformat(),
                            "until": req.requested_ends_on.isoformat(),
                        },
                        separators=(",", ":"),
                    ),
                }
                if requested_cursor:
                    params["after"] = requested_cursor
                page = parse_selected_page(
                    read("/insights", params, 2_000_000),
                    req,
                    mapping,
                    requested_cursor=requested_cursor,
                )
                check()
                return page
        except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
            raise MetaSelectedReadUnavailable("meta_selected_read_unavailable") from None
        finally:
            _private_http.reset(private)
