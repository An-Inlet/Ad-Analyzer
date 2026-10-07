"""Transport/parser resource limits only; fake contexts do not prove ownership."""

from datetime import timedelta
from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest
from app.collectors import tiktok_linked_posts as posts
from app.collectors.tiktok_owned_discovery import TikTokDiscoveryUnavailable
from app.production_runtime.owned_tiktok_contexts import OwnedTikTokContexts
from app.publication.execution_contracts import ExecutionAccount
from app.publication.tiktok_linked_contracts import TikTokUserIdentityV1
from pydantic import SecretStr

from tests.test_commerce_measurement import NOW
from tests.test_tiktok_linked_posts_contracts import body
from tests.test_tiktok_linked_posts_owned import wire_bytes


@pytest.mark.parametrize(
    "failure",
    [
        "page_bytes",
        "total_bytes",
        "pages",
        "cycle",
        "duplicate_post",
        "duplicate_json",
        "redirect",
        "nan",
        "deadline",
        "late_close",
        "credential_expiry",
    ],
)
def test_bounded_read_has_no_partial_catalogue(
    failure: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    current, ticks = [NOW], [0.0]
    calls: list[httpx.Request] = []
    closed: list[bool] = []
    monkeypatch.setattr(posts, "monotonic", lambda: ticks[0])
    if failure == "pages":
        monkeypatch.setattr(posts, "MAX_PAGES", 2)
    if failure == "total_bytes":
        monkeypatch.setattr(posts, "MAX_TOTAL_BYTES", 900)

    class Context:
        manifest = SimpleNamespace(environment="contract_test")

        def credentials(self, scope: ExecutionAccount) -> tuple[SecretStr, Any]:
            return SecretStr("offline-boundary-token"), NOW + timedelta(seconds=5)

    scope = ExecutionAccount.model_validate(
        dict(
            workspace_id=1,
            account=dict(platform="tiktok_ads", account_id=2, connection_id=3),
            external_advertiser_id="123",
            connection_version="v1",
        )
    )

    def wire(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if failure == "page_bytes":
            return httpx.Response(200, content=b" " * (posts.MAX_PAGE_BYTES + 1))
        if failure == "redirect":
            return httpx.Response(302, headers={"Location": "https://untrusted.example"})
        if failure == "duplicate_json":
            return httpx.Response(200, content=b'{"code":0,"code":0,"data":{}}')
        if failure == "nan":
            return httpx.Response(200, content=b'{"code":0,"data":{"cursor":NaN}}')
        if failure == "deadline":
            ticks[0] = 31
        if failure == "credential_expiry":
            current[0] += timedelta(seconds=6)
        more = failure in {"pages", "cycle", "duplicate_post", "total_bytes"}
        cursor = "100" if failure == "cycle" else str(100 - len(calls))
        identifier = "same" if failure == "duplicate_post" else f"post-{len(calls)}"
        return httpx.Response(
            200, content=wire_bytes(body(cursor=cursor, more=more, identifier=identifier))
        )

    class Transport(httpx.MockTransport):
        def close(self) -> None:
            closed.append(True)
            if failure == "late_close":
                current[0] += timedelta(seconds=6)
            super().close()

    reader = posts.TikTokLinkedPosts(
        scope, cast(OwnedTikTokContexts, Context()), Transport(wire), lambda: current[0]
    )
    with pytest.raises(TikTokDiscoveryUnavailable):
        reader.videos(
            TikTokUserIdentityV1(identity_type="TT_USER", identity_id="linked-1"),
            exclude_adsonly=True,
        )
    assert closed == [True] and len(calls) <= 2


@pytest.mark.parametrize("environment, mock", [("live", True), ("contract_test", False)])
def test_constructor_denies_live_or_nonmock_before_credentials(
    environment: str, mock: bool
) -> None:
    class Context:
        manifest = SimpleNamespace(environment=environment)

        def credentials(self, scope: ExecutionAccount) -> tuple[SecretStr, Any]:
            raise AssertionError("credentials must not be read")

    scope = ExecutionAccount.model_validate(
        dict(
            workspace_id=1,
            account=dict(platform="tiktok_ads", account_id=2, connection_id=3),
            external_advertiser_id="123",
            connection_version="v1",
        )
    )
    transport = (
        httpx.MockTransport(lambda _: pytest.fail("HTTP must not run")) if mock else object()
    )
    with pytest.raises(TikTokDiscoveryUnavailable):
        posts.TikTokLinkedPosts(
            scope,
            cast(OwnedTikTokContexts, Context()),
            cast(httpx.MockTransport, transport),
            lambda: NOW,
        )
