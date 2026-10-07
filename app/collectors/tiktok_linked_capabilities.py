"""Owned bounded linked identity/capability reads; explicit offline transports only."""

import json
from collections.abc import Callable
from datetime import datetime, timedelta
from time import monotonic
from typing import Any

import httpx
from pydantic import SecretStr

from app.collectors.tiktok_discovery_parser import IDENTITY_STATUS, object_value
from app.collectors.tiktok_owned_discovery import (
    _nonfinite,
    _unique_object,
    unavailable,
)
from app.production_runtime.owned_tiktok_contexts import OwnedTikTokContexts
from app.publication.execution_contracts import ExecutionAccount
from app.publication.tiktok_linked_contracts import (
    AdvertiserCapabilitiesObservationV1,
    AdvertiserCapabilitiesRequestV1,
    IdentityInfoObservationV1,
    IdentityInfoRequestV1,
    LinkedIdentityV1,
    LinkedOwnerV1,
    ObservedBooleanV1,
)

MAX_BYTES = 262_144
MAX_SECONDS = 10


def boolean(row: dict[str, Any], name: str) -> ObservedBooleanV1:
    return ObservedBooleanV1(
        presence="absent" if name not in row else "null" if row[name] is None else "present",
        value=row.get(name),
    )


def data(payload: object) -> dict[str, Any]:
    envelope = object_value(payload)
    if type(envelope.get("code")) is not int or envelope["code"] != 0:
        raise unavailable()
    return object_value(envelope.get("data"))


class TikTokLinkedCapabilities:
    def __init__(
        self,
        scope: ExecutionAccount,
        contexts: OwnedTikTokContexts,
        transport: httpx.MockTransport,
        clock: Callable[[], datetime],
    ) -> None:
        if (
            not isinstance(transport, httpx.MockTransport)
            or contexts.manifest.environment != "contract_test"
            or scope.account.platform != "tiktok_ads"
        ):
            raise unavailable()
        self.scope = ExecutionAccount.model_validate_json(scope.model_dump_json())
        self.owner = LinkedOwnerV1(
            workspace_id=scope.workspace_id,
            account_id=scope.account.account_id,
            connection_id=scope.account.connection_id,
            external_advertiser_id=scope.external_advertiser_id,
            connection_version=scope.connection_version,
        )
        self.contexts, self.transport, self.clock = contexts, transport, clock

    def identity(self, identity: LinkedIdentityV1) -> IdentityInfoObservationV1:
        request = IdentityInfoRequestV1(owner=self.owner, identity=identity)
        params = {"advertiser_id": self.owner.external_advertiser_id, **identity.model_dump()}
        try:
            raw, observed, expiry = self._read("identity/info/", params)
            body = data(raw)
            row = object_value(body.get("identity_info"))
            for key, value in identity.model_dump().items():
                if row.get(key) != value:
                    raise unavailable()
            if (
                identity.identity_type == "TT_USER"
                and row.get("identity_authorized_bc_id") is not None
            ):
                raise unavailable()
            for part in (body, row):
                if (
                    "advertiser_id" in part
                    and part["advertiser_id"] != self.owner.external_advertiser_id
                ):
                    raise unavailable()
            status = row.get("available_status")
            if status is not None and (type(status) is not str or len(status) > 128):
                raise unavailable()
            normalized = (
                "absent"
                if "available_status" not in row
                else "null"
                if status is None
                else status
                if status in IDENTITY_STATUS
                else "unknown"
            )
            return IdentityInfoObservationV1.model_validate(
                {
                    "request": request,
                    "observed_at": observed,
                    "expires_at": expiry,
                    "available_status": normalized,
                    **{
                        name: boolean(row, name)
                        for name in (
                            "is_gpppa",
                            "can_push_video",
                            "can_pull_video",
                            "ads_only_mode",
                        )
                    },
                }
            )
        except (ValueError, TypeError, KeyError, RecursionError):
            raise unavailable() from None

    def advertiser(self) -> AdvertiserCapabilitiesObservationV1:
        request = AdvertiserCapabilitiesRequestV1(
            owner=self.owner, fields=("ads_only_mode", "can_use_custom_identity")
        )
        try:
            raw, observed, expiry = self._read(
                "advertiser/info/",
                {
                    "advertiser_ids": json.dumps(
                        [self.owner.external_advertiser_id], separators=(",", ":")
                    ),
                    "fields": json.dumps(request.fields, separators=(",", ":")),
                },
            )
            rows = data(raw).get("list")
            if not isinstance(rows, list) or len(rows) != 1:
                raise unavailable()
            row = object_value(rows[0])
            if row.get("advertiser_id") != self.owner.external_advertiser_id:
                raise unavailable()
            return AdvertiserCapabilitiesObservationV1(
                request=request,
                observed_at=observed,
                expires_at=expiry,
                ads_only_mode=boolean(row, "ads_only_mode"),
                can_use_custom_identity=boolean(row, "can_use_custom_identity"),
            )
        except (ValueError, TypeError, KeyError, RecursionError):
            raise unavailable() from None

    def _read(self, path: str, params: dict[str, Any]) -> tuple[object, datetime, datetime]:
        started, deadline = self.clock(), monotonic() + MAX_SECONDS
        original: tuple[SecretStr, datetime] | None = None
        expiry: datetime | None = None

        def remaining() -> float:
            seconds, now = deadline - monotonic(), self.clock()
            if (
                seconds <= 0
                or now.tzinfo is None
                or now < started
                or (expiry is not None and now >= expiry)
            ):
                raise unavailable()
            return seconds

        def checkpoint() -> SecretStr:
            nonlocal original, expiry
            remaining()
            token, until = self.contexts.credentials(self.scope)
            if original is None:
                original = token, until
                expiry = min(until, started + timedelta(minutes=5))
            elif token != original[0]:
                raise unavailable()
            assert expiry is not None
            expiry = min(expiry, until)
            remaining()
            return token

        try:
            with httpx.Client(
                transport=self.transport, follow_redirects=False, trust_env=False
            ) as client:
                token = checkpoint()
                seconds = remaining()
                with client.stream(
                    "GET",
                    "https://business-api.tiktok.com/open_api/v1.3/" + path,
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
                        if len(raw) + len(chunk) > MAX_BYTES:
                            raise unavailable()
                        raw.extend(chunk)
                    payload = json.loads(
                        raw, object_pairs_hook=_unique_object, parse_constant=_nonfinite
                    )
                checkpoint()
            checkpoint()  # Closing the transport can block or revoke authority too.
            assert expiry is not None
            return payload, self.clock(), expiry
        except (httpx.HTTPError, ValueError, TypeError, KeyError, RecursionError):
            raise unavailable() from None
