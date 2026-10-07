"""Bounded owned GET discovery, currently explicit contract-test transports only."""

import json
from collections.abc import Callable
from datetime import datetime
from time import monotonic
from typing import Any, Literal, NoReturn, overload

import httpx
from pydantic import SecretStr

from app.collectors.tiktok_discovery_contracts import (
    IdentityType,
    TikTokIdentityPageRequestV1,
    TikTokIdentityPageV1,
    TikTokPixelPageRequestV1,
    TikTokPixelPageV1,
)
from app.collectors.tiktok_discovery_parser import parse_identity_page, parse_pixel_page
from app.collectors.tiktok_owned_discovery_contracts import (
    TikTokDiscoveryScopeV1,
    TikTokIdentityDiscoveryV1,
    TikTokPixelDiscoveryV1,
)
from app.production_runtime.owned_tiktok_contexts import OwnedTikTokContexts
from app.publication.execution_contracts import ExecutionAccount

MAX_PAGES = 10
MAX_PAGE_BYTES = 2_000_000
MAX_TOTAL_BYTES = 8_000_000
MAX_SECONDS = 30


class TikTokDiscoveryUnavailable(RuntimeError):
    """Sanitized discovery failure; no partial inventory or provider content."""


def unavailable() -> TikTokDiscoveryUnavailable:
    return TikTokDiscoveryUnavailable("tiktok_owned_discovery_unavailable")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise unavailable()
        result[key] = value
    return result


def _nonfinite(value: str) -> NoReturn:
    raise unavailable()


class TikTokOwnedDiscovery:
    def __init__(
        self,
        scope: ExecutionAccount,
        contexts: OwnedTikTokContexts,
        transport: httpx.MockTransport,
        clock: Callable[[], datetime],
    ) -> None:
        if not isinstance(transport, httpx.MockTransport) or (
            contexts.manifest.environment != "contract_test"
        ):
            raise unavailable()
        self._scope = ExecutionAccount.model_validate_json(scope.model_dump_json())
        self.scope = TikTokDiscoveryScopeV1.from_account(self._scope)
        self.contexts, self.transport, self.clock = contexts, transport, clock

    def identities(
        self,
        identity_type: IdentityType,
        *,
        identity_authorized_bc_id: str | None = None,
    ) -> TikTokIdentityDiscoveryV1:
        request = TikTokIdentityPageRequestV1(
            advertiser_id=self.scope.external_advertiser_id,
            identity_type=identity_type,
            identity_authorized_bc_id=identity_authorized_bc_id,
            page=1,
            page_size=100,
        )
        return self._collect("identity", request)

    def pixels(self) -> TikTokPixelDiscoveryV1:
        request = TikTokPixelPageRequestV1(
            advertiser_id=self.scope.external_advertiser_id,
            page=1,
            page_size=20,
            order_by="EARLIEST_CREATE",
            available_for_catalog_only=False,
        )
        return self._collect("pixel", request)

    @overload
    def _collect(
        self, kind: Literal["identity"], request: TikTokIdentityPageRequestV1
    ) -> TikTokIdentityDiscoveryV1: ...

    @overload
    def _collect(
        self, kind: Literal["pixel"], request: TikTokPixelPageRequestV1
    ) -> TikTokPixelDiscoveryV1: ...

    def _collect(
        self,
        kind: Literal["identity", "pixel"],
        request: TikTokIdentityPageRequestV1 | TikTokPixelPageRequestV1,
    ) -> TikTokIdentityDiscoveryV1 | TikTokPixelDiscoveryV1:
        started, deadline = self.clock(), monotonic() + MAX_SECONDS
        original: tuple[SecretStr, datetime] | None = None
        total_bytes = 0

        def remaining() -> float:
            seconds = deadline - monotonic()
            now = self.clock()
            if (
                seconds <= 0
                or now.tzinfo is None
                or now < started
                or (original is not None and now >= original[1])
            ):
                raise unavailable()
            return seconds

        def checkpoint() -> SecretStr:
            nonlocal original
            remaining()
            token, expiry = self.contexts.credentials(self._scope)
            if original is None:
                original = token, expiry
            if token != original[0] or expiry <= self.clock():
                raise unavailable()
            remaining()
            return token

        identities: list[TikTokIdentityPageV1] = []
        pixels: list[TikTokPixelPageV1] = []
        expected_pages: int | None = None
        try:
            with httpx.Client(
                transport=self.transport, follow_redirects=False, trust_env=False
            ) as client:
                for number in range(1, MAX_PAGES + 1):
                    token = checkpoint()
                    params: dict[str, Any] = {
                        "advertiser_id": self.scope.external_advertiser_id,
                        "page": number,
                        "page_size": request.page_size,
                    }
                    if isinstance(request, TikTokIdentityPageRequestV1):
                        params["identity_type"] = request.identity_type
                        if request.identity_authorized_bc_id is not None:
                            params["identity_authorized_bc_id"] = request.identity_authorized_bc_id
                    else:
                        params["order_by"] = request.order_by
                        params["filtering"] = json.dumps(
                            {"available_for_catalog_only": False}, separators=(",", ":")
                        )
                    seconds = remaining()
                    with client.stream(
                        "GET",
                        f"https://business-api.tiktok.com/open_api/v1.3/{kind}/"
                        + ("get/" if kind == "identity" else "list/"),
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
                            raw, object_pairs_hook=_unique_object, parse_constant=_nonfinite
                        )
                    checkpoint()
                    if not isinstance(payload, dict):
                        raise unavailable()
                    data = payload.get("data")
                    if isinstance(data, dict):
                        rows = data.get("identity_list" if kind == "identity" else "pixels", [])
                        for row in [data, *(rows if isinstance(rows, list) else [])]:
                            if (
                                isinstance(row, dict)
                                and "advertiser_id" in row
                                and (row["advertiser_id"] != self.scope.external_advertiser_id)
                            ):
                                raise unavailable()
                    if isinstance(request, TikTokIdentityPageRequestV1):
                        page = parse_identity_page(
                            request.model_copy(update={"page": number}), payload
                        )
                        identities.append(page)
                        info = page.page_info
                    else:
                        pixel_page = parse_pixel_page(
                            request.model_copy(update={"page": number}), payload
                        )
                        pixels.append(pixel_page)
                        info = pixel_page.page_info
                    count = max(1, (info.total_number + info.page_size - 1) // info.page_size)
                    if count > MAX_PAGES or (
                        expected_pages is not None and count != expected_pages
                    ):
                        raise unavailable()
                    expected_pages = count
                    if number == expected_pages:
                        break
                remaining()
                if kind == "identity":
                    result: TikTokIdentityDiscoveryV1 | TikTokPixelDiscoveryV1 = (
                        TikTokIdentityDiscoveryV1(
                            scope=self.scope,
                            pages=tuple(identities),
                            observed_started_at=started,
                            observed_ended_at=self.clock(),
                        )
                    )
                else:
                    result = TikTokPixelDiscoveryV1(
                        scope=self.scope,
                        pages=tuple(pixels),
                        observed_started_at=started,
                        observed_ended_at=self.clock(),
                    )
                checkpoint()
            checkpoint()  # Transport close may itself delay or change authority.
            return result
        except (httpx.HTTPError, ValueError, TypeError, KeyError, RecursionError):
            raise unavailable() from None
