"""Bounded Meta v26 account-edge discovery. No factory, mutations or qualification."""

import hashlib
import hmac
import json
import re
import unicodedata
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Any

import httpx
from pydantic import AwareDatetime, Field, SecretStr

from app.executors.social_http import _private_http
from app.goals.schemas import StrictModel
from app.publication.execution_contracts import ExecutionAccount
from app.publication.provider_contracts import Digest
from app.publication.social_catalog import (
    MetaCatalogOption,
    MetaConfigurationProfile,
    SocialCatalog,
    SocialCatalogRequest,
)


class MetaCatalogUnavailable(RuntimeError):
    """Fixed codes only; raw provider bodies and identifiers must not escape."""


class MetaCatalogContext(StrictModel):
    account: ExecutionAccount
    request_digest: Digest
    expires_at: AwareDatetime
    access_token: SecretStr = Field(exclude=True, repr=False)
    app_secret: SecretStr | None = Field(default=None, exclude=True, repr=False)


class MetaCatalogHTTP:
    def __init__(
        self,
        context_reader: Callable[[SocialCatalogRequest, datetime], MetaCatalogContext],
        profiles: Sequence[MetaConfigurationProfile],
        *,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if len(profiles) > 10:
            raise ValueError("catalog profile bound exceeded")
        self.context_reader = context_reader
        self.profiles = tuple(
            MetaConfigurationProfile.model_validate(p.model_dump()) for p in profiles
        )
        self.transport, self.clock = transport, clock

    def __call__(self, request: SocialCatalogRequest, now: datetime, /) -> SocialCatalog:
        request = SocialCatalogRequest.model_validate(request.model_dump())
        if request.account.account.platform != "meta_ads":
            raise MetaCatalogUnavailable("catalog_platform_invalid")
        context = self.context_reader(request, now)
        if (
            context.account != request.account
            or context.request_digest != request.digest()
            or not context.access_token.get_secret_value()
        ):
            raise MetaCatalogUnavailable("catalog_context_invalid")
        expires = min(now + timedelta(minutes=5), context.expires_at)
        deadline, calls, total_bytes = monotonic() + 60, 0, 0

        def check() -> None:
            if not now <= self.clock() < expires or monotonic() >= deadline:
                raise MetaCatalogUnavailable("catalog_expired")

        check()
        headers = {
            "Authorization": "Bearer " + context.access_token.get_secret_value(),
            "Accept-Encoding": "identity",
        }
        proof = {}
        if context.app_secret is not None:
            proof["appsecret_proof"] = hmac.new(
                context.app_secret.get_secret_value().encode(),
                context.access_token.get_secret_value().encode(),
                hashlib.sha256,
            ).hexdigest()
        base = "https://graph.facebook.com/v26.0/act_" + request.account.external_advertiser_id
        private = _private_http.set(True)
        try:
            with httpx.Client(
                transport=self.transport,
                timeout=httpx.Timeout(12, connect=5),
                follow_redirects=False,
                trust_env=False,
            ) as client:

                def get(suffix: str, params: dict[str, str]) -> dict[str, Any]:
                    nonlocal calls, total_bytes
                    check()
                    calls += 1
                    if calls > 21:
                        raise MetaCatalogUnavailable("catalog_request_bound")
                    with client.stream(
                        "GET", base + suffix, params={**params, **proof}, headers=headers
                    ) as response:
                        if (
                            response.status_code != 200
                            or response.headers.get("Content-Encoding", "identity") != "identity"
                        ):
                            raise MetaCatalogUnavailable("catalog_provider_unavailable")
                        raw = bytearray()
                        for chunk in response.iter_bytes():
                            check()
                            raw.extend(chunk)
                            total_bytes += len(chunk)
                            if len(raw) > 1_000_000 or total_bytes > 4_000_000:
                                raise MetaCatalogUnavailable("catalog_response_bound")
                    check()
                    data = json.loads(raw)
                    if not isinstance(data, dict) or "error" in data:
                        raise MetaCatalogUnavailable("catalog_response_invalid")
                    return data

                account = get("", {"fields": "account_id,currency,timezone_name,account_status"})
                if (
                    account.get("account_id") != request.account.external_advertiser_id
                    or type(account.get("account_status")) is not int
                    or account["account_status"] != 1
                ):
                    raise MetaCatalogUnavailable("catalog_account_unavailable")

                def inventory(edge: str) -> list[tuple[str, str]]:
                    params = {"fields": "id,name", "limit": "100"}
                    result: list[tuple[str, str]] = []
                    ids: set[str] = set()
                    cursors: set[str] = set()
                    for _ in range(10):
                        data = get(edge, params)
                        rows = data.get("data")
                        if not isinstance(rows, list):
                            raise MetaCatalogUnavailable("catalog_response_invalid")
                        for row in rows:
                            if not isinstance(row, dict):
                                raise MetaCatalogUnavailable("catalog_response_invalid")
                            identifier, name = row.get("id"), row.get("name")
                            if (
                                not isinstance(identifier, str)
                                or not re.fullmatch(r"[0-9]{1,32}", identifier)
                                or identifier in ids
                                or not isinstance(name, str)
                                or not 1 <= len(name.strip()) <= 120
                                or any(unicodedata.category(c).startswith("C") for c in name)
                            ):
                                raise MetaCatalogUnavailable("catalog_resource_invalid")
                            ids.add(identifier)
                            result.append((identifier, name.strip()))
                            if len(result) > 100:
                                raise MetaCatalogUnavailable("catalog_inventory_bound")
                        paging = data.get("paging", {})
                        if not isinstance(paging, dict):
                            raise MetaCatalogUnavailable("catalog_pagination_invalid")
                        if not paging.get("next"):
                            return result
                        cursor_map = paging.get("cursors")
                        cursor = cursor_map.get("after") if isinstance(cursor_map, dict) else None
                        if (
                            not isinstance(cursor, str)
                            or not 1 <= len(cursor) <= 1024
                            or cursor in cursors
                        ):
                            raise MetaCatalogUnavailable("catalog_pagination_invalid")
                        cursors.add(cursor)
                        params["after"] = cursor
                    raise MetaCatalogUnavailable("catalog_page_bound")

                pages, pixels = inventory("/promote_pages"), inventory("/adspixels")
                profiles = [
                    p
                    for p in self.profiles
                    if p.currency == account.get("currency")
                    and set(p.language_locale_ids) == set(request.languages)
                ]
                if len(pages) * len(pixels) * len(profiles) > 50:
                    raise MetaCatalogUnavailable("catalog_option_bound")
                options = [
                    MetaCatalogOption(
                        label=(page_name + " / " + pixel_name + " / " + p.label)[:160],
                        profile_digest=p.digest(),
                        page_id=page_id,
                        pixel_id=pixel_id,
                    )
                    for page_id, page_name in pages
                    for pixel_id, pixel_name in pixels
                    for p in profiles
                ]
                check()
                return SocialCatalog(
                    request=request,
                    observed_at=now,
                    expires_at=expires,
                    currency=account["currency"],
                    account_timezone=account["timezone_name"],
                    options=options,
                    unavailable_reasons=[]
                    if options
                    else ["supported_social_configuration_unavailable"],
                    qualification_blockers=[
                        "native_configuration_unqualified",
                        "conversion_eligibility_unverified",
                        "audience_mapping_qualification_required",
                        "customer_declaration_required",
                    ],
                    discovery_evidence="meta_account_edges",
                )
        except MetaCatalogUnavailable:
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise MetaCatalogUnavailable("catalog_provider_unavailable") from None
        finally:
            _private_http.reset(private)
