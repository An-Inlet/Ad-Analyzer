"""Actual owned vault/session + MockTransport reads, with no runtime getter override."""

import json
import time
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.collectors import tiktok_owned_discovery as discovery
from app.customers.access import SESSION_COOKIE, CustomerPrincipal, digest
from app.customers.models import CustomerSession, CustomerUser
from app.production_runtime.owned_tiktok_contexts import OwnedTikTokContexts
from app.production_runtime.tiktok_configuration import load_tiktok_execution_configuration
from app.publication.customer_authority import bind_authority
from app.publication.customer_intents import account
from app.settings import Settings, settings
from app.sources.models import SourceConnection
from app.sources.security import SourceVault
from fastapi import HTTPException
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration
from tests.tiktok_read_fixture import prepare_tiktok_read_source
from tests.tiktok_read_fixture import read_only_graph as read_only_graph

pytestmark = [pytest.mark.planning_boundary, pytest.mark.usefixtures("read_only_graph")]


def prepare(
    engine: Engine,
    configuration: Settings,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    video: bytes | None = None,
) -> tuple[Any, OwnedTikTokContexts, Any]:
    prepare_tiktok_read_source(
        engine,
        configuration,
        path,
        monkeypatch,
        replicas,
    )
    alice = replicas[0]
    with Session(engine) as db:
        source = db.scalar(
            select(SourceConnection).where(SourceConnection.provider == "tiktok_ads")
        )
        assert source and source.account_id
        scope = account(db, source.workspace_id, source.account_id)
        original = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
        assert original
        user = db.get(CustomerUser, original.user_id)
        assert user
        principal = CustomerPrincipal(user, original)
        authorize = bind_authority(principal, replicas[2])
    configured = load_tiktok_execution_configuration(
        settings.tiktok_execution_manifest_path,
        settings.tiktok_execution_manifest_digest,
        settings.tiktok_execution_bundle_path,
    )
    assert configured
    contexts = OwnedTikTokContexts(
        sessionmaker(engine), authorize, principal.user.id, configured[0], settings, lambda: NOW
    )
    return scope, contexts, alice


def response(request: httpx.Request, *, total: int = 21) -> dict[str, Any]:
    number, size = int(request.url.params["page"]), int(request.url.params["page_size"])
    identities = request.url.path.endswith("identity/get/")
    start, end = (number - 1) * size, min(number * size, total)
    rows: list[dict[str, Any]] = [
        {
            "identity_id": str(i),
            "identity_type": request.url.params["identity_type"],
            **(
                {"identity_authorized_bc_id": request.url.params["identity_authorized_bc_id"]}
                if "identity_authorized_bc_id" in request.url.params
                else {}
            ),
        }
        if identities
        else {"pixel_id": str(i), "events": None}
        for i in range(start, end)
    ]
    return {
        "code": 0,
        "data": {
            "identity_list" if identities else "pixels": rows,
            "page_info": {
                "page": number,
                "page_size": size,
                "total_number": total,
                "total_page": (total + size - 1) // size,
            },
        },
    }


@pytest.mark.parametrize("kind", ["pixel", "identity", "empty"])
def test_owned_get_traversal(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    kind: str,
) -> None:
    scope, contexts, _ = prepare(customer_engine, configuration, tmp_path, monkeypatch, replicas)
    requests: list[httpx.Request] = []
    closed: list[bool] = []

    def wire(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "GET"
        assert request.url.host == "business-api.tiktok.com"
        assert request.headers["Access-Token"] == "offline-tiktok-access"
        assert request.url.params["advertiser_id"] == scope.external_advertiser_id
        if kind == "identity":
            assert request.url.params["identity_type"] == "BC_AUTH_TT"
            assert request.url.params["identity_authorized_bc_id"] == "123"
        else:
            assert json.loads(request.url.params["filtering"]) == {
                "available_for_catalog_only": False
            }
        return httpx.Response(200, json=response(request, total=0 if kind == "empty" else 101))

    class Transport(httpx.MockTransport):
        def close(self) -> None:
            closed.append(True)
            super().close()

    reader = discovery.TikTokOwnedDiscovery(scope, contexts, Transport(wire), lambda: NOW)
    result = (
        reader.identities("BC_AUTH_TT", identity_authorized_bc_id="123")
        if kind == "identity"
        else reader.pixels()
    )
    assert result.traversal_completeness == "complete_requested_scope"
    assert result.publication_eligibility == "not_assessed"
    assert result.spending_authority == "none"
    assert len(requests) == (2 if kind == "identity" else 1 if kind == "empty" else 6)
    assert len(closed) == 1
    contexts.close()


@pytest.mark.parametrize("change", ["revoke", "generation", "profile", "token", "expiry", "close"])
def test_owned_change_during_io_discards_every_result(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    change: str,
) -> None:
    scope, contexts, alice = prepare(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
    )
    calls: list[httpx.Request] = []
    closed: list[bool] = []

    def invalidate() -> None:
        if change == "profile":
            monkeypatch.setattr(settings, "tiktok_execution_manifest_digest", "f" * 64)
            return
        with Session(customer_engine) as db:
            if change in {"revoke", "close"}:
                session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
                assert session
                session.revoked_at = int(time.time())
            else:
                source = db.scalar(
                    select(SourceConnection).where(SourceConnection.provider == "tiktok_ads")
                )
                assert source and source.encrypted_grant
                if change == "generation":
                    source.generation += 1
                else:
                    grant = SourceVault().open(
                        source.workspace_id, source.provider, source.id, source.encrypted_grant
                    )
                    if change == "token":
                        grant["access_token"] = "different-offline-token"
                    else:
                        grant["expires_at"] = (NOW - timedelta(seconds=1)).isoformat()
                    source.encrypted_grant = SourceVault().seal(
                        source.workspace_id, source.provider, source.id, grant
                    )
            db.commit()

    def wire(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if change != "close":
            invalidate()
        return httpx.Response(200, json=response(request, total=1))

    class Transport(httpx.MockTransport):
        def close(self) -> None:
            closed.append(True)
            if change == "close":
                invalidate()
            super().close()

    reader = discovery.TikTokOwnedDiscovery(scope, contexts, Transport(wire), lambda: NOW)
    with pytest.raises((HTTPException, discovery.TikTokDiscoveryUnavailable)):
        reader.pixels()
    assert len(calls) == len(closed) == 1
    contexts.close()


@pytest.mark.parametrize(
    "failure",
    [
        "duplicate",
        "totals",
        "missing_id",
        "foreign",
        "status",
        "oversize",
        "total_bytes",
        "deadline",
        "many_pages",
        "duplicate_key",
        "nonfinite",
        "deep",
    ],
)
def test_bounded_inconsistent_wire_never_returns_complete(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    failure: str,
) -> None:
    scope, contexts, _ = prepare(customer_engine, configuration, tmp_path, monkeypatch, replicas)
    calls: list[httpx.Request] = []
    closed: list[bool] = []
    mono = [0.0]
    monkeypatch.setattr(discovery, "monotonic", lambda: mono[0])
    if failure == "oversize":
        monkeypatch.setattr(discovery, "MAX_PAGE_BYTES", 10)

    def wire(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        document = response(request, total=201 if failure == "many_pages" else 21)
        if failure == "deadline":
            mono[0] = 31
        if failure == "foreign":
            document["data"]["advertiser_id"] = "foreign"
        if failure == "missing_id":
            document["data"]["pixels"][0].pop("pixel_id")
        if len(calls) == 2:
            if failure == "duplicate":
                document["data"]["pixels"][0]["pixel_id"] = "0"
            if failure == "totals":
                document["data"]["page_info"]["total_number"] = 22
        if failure == "duplicate_key":
            raw = json.dumps(document).replace('"code": 0', '"code": 1, "code": 0')
            return httpx.Response(200, content=raw)
        if failure == "nonfinite":
            return httpx.Response(200, content=json.dumps(document)[:-1] + ', "extra": NaN}')
        if failure == "deep":
            return httpx.Response(200, content="[" * 1200 + "0" + "]" * 1200)
        result = httpx.Response(302 if failure == "status" else 200, json=document)
        if failure == "total_bytes" and len(calls) == 1:
            monkeypatch.setattr(discovery, "MAX_TOTAL_BYTES", len(result.content) + 1)
        return result

    class Transport(httpx.MockTransport):
        def close(self) -> None:
            closed.append(True)
            super().close()

    reader = discovery.TikTokOwnedDiscovery(scope, contexts, Transport(wire), lambda: NOW)
    with pytest.raises(discovery.TikTokDiscoveryUnavailable):
        reader.pixels()
    assert 1 <= len(calls) <= 2
    assert len(closed) == 1
    contexts.close()


@pytest.mark.parametrize("delay", ["context", "stream"])
def test_elapsed_context_or_stream_delay_discards_and_closes(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    delay: str,
) -> None:
    scope, contexts, _ = prepare(customer_engine, configuration, tmp_path, monkeypatch, replicas)
    mono = [0.0]
    monkeypatch.setattr(discovery, "monotonic", lambda: mono[0])
    calls: list[httpx.Request] = []
    closed: list[str] = []
    credentials = contexts.credentials
    if delay == "context":

        def delayed(actual: Any) -> Any:
            value = credentials(actual)
            mono[0] = 31
            return value

        monkeypatch.setattr(contexts, "credentials", delayed)

    class Stream(httpx.SyncByteStream):
        def __iter__(self) -> Any:
            yield b'{"code":'
            mono[0] = 31
            yield b"0}"

        def close(self) -> None:
            closed.append("stream")

    def wire(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, stream=Stream())

    class Transport(httpx.MockTransport):
        def close(self) -> None:
            closed.append("transport")
            super().close()

    real = httpx.HTTPTransport()
    try:
        with pytest.raises(discovery.TikTokDiscoveryUnavailable):
            discovery.TikTokOwnedDiscovery(scope, contexts, real, lambda: NOW)  # type: ignore[arg-type]
    finally:
        real.close()
    manifest = contexts.manifest
    contexts.manifest = manifest.model_copy(update={"environment": "live"})
    with pytest.raises(discovery.TikTokDiscoveryUnavailable):
        discovery.TikTokOwnedDiscovery(scope, contexts, Transport(wire), lambda: NOW)
    contexts.manifest = manifest
    reader = discovery.TikTokOwnedDiscovery(scope, contexts, Transport(wire), lambda: NOW)
    with pytest.raises(discovery.TikTokDiscoveryUnavailable):
        reader.pixels()
    assert len(calls) == (1 if delay == "stream" else 0)
    assert closed == (["stream", "transport"] if delay == "stream" else ["transport"])
    contexts.close()


@pytest.mark.parametrize("change", ["workspace", "generation"])
def test_wrong_owned_scope_denied_before_first_http(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    change: str,
) -> None:
    scope, contexts, _ = prepare(customer_engine, configuration, tmp_path, monkeypatch, replicas)
    wrong = (
        scope.model_copy(update={"workspace_id": scope.workspace_id + 99999})
        if (change == "workspace")
        else scope.model_copy(update={"connection_version": "foreign-generation"})
    )
    calls: list[httpx.Request] = []

    def wire(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=response(request))

    reader = discovery.TikTokOwnedDiscovery(wrong, contexts, httpx.MockTransport(wire), lambda: NOW)
    with pytest.raises(HTTPException) as error:
        reader.pixels()
    assert error.value.status_code in {401, 403, 404, 409}
    assert calls == []
    contexts.close()
