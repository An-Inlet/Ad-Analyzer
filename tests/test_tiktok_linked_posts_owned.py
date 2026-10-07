"""Actual original-session/source/vault guards around bounded mock native VIDEO GETs."""

import json
import time
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.collectors import tiktok_linked_posts as posts
from app.collectors.tiktok_owned_discovery import TikTokDiscoveryUnavailable
from app.customers.access import SESSION_COOKIE, digest
from app.customers.models import CustomerSession
from app.publication.tiktok_linked_contracts import TikTokBusinessIdentityV1, TikTokUserIdentityV1
from app.settings import Settings, settings
from app.sources.models import SourceConnection
from fastapi import HTTPException
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_campaign_video import encoded as encoded
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration
from tests.test_tiktok_linked_posts_contracts import body
from tests.test_tiktok_owned_discovery import prepare


def wire_bytes(payload: object) -> bytes:
    # Exact JSON number literal, not a binary-float round trip.
    return (
        json.dumps(payload, default=str)
        .replace('"duration": "12.123456789012345678901"', '"duration": 12.123456789012345678901')
        .encode()
    )


@pytest.mark.parametrize("kind", ["TT_USER", "BC_AUTH_TT"])
def test_actual_owned_video_pagination(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    encoded: Any,
    kind: str,
) -> None:
    scope, contexts, _ = prepare(
        customer_engine, configuration, tmp_path, monkeypatch, replicas, encoded()
    )
    identity = (
        TikTokUserIdentityV1(identity_type="TT_USER", identity_id="linked-1")
        if kind == "TT_USER"
        else TikTokBusinessIdentityV1(
            identity_type="BC_AUTH_TT", identity_id="linked-1", identity_authorized_bc_id="bc-1"
        )
    )
    calls: list[httpx.Request] = []
    closed: list[bool] = []

    def wire(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.method == "GET" and str(request.url).startswith(posts.ENDPOINT)
        assert request.headers["Access-Token"] == "offline-tiktok-access"
        assert request.url.params["advertiser_id"] == scope.external_advertiser_id
        assert request.url.params["identity_id"] == "linked-1"
        assert request.url.params["identity_type"] == kind
        assert request.url.params["item_type"] == "VIDEO"
        assert request.url.params["exclude_adsonly"] == "false"
        assert request.url.params["count"] == "20"
        assert "keyword" not in request.url.params and "page_info" not in request.url.params
        if kind == "BC_AUTH_TT":
            assert request.url.params["identity_authorized_bc_id"] == "bc-1"
        else:
            assert "identity_authorized_bc_id" not in request.url.params
        if len(calls) == 1:
            assert "cursor" not in request.url.params
            value = body(cursor="900719925474099312345", more=True)
        else:
            assert request.url.params["cursor"] == "900719925474099312345"
            value = body(cursor="900719925474099312344", identifier="post-2")
        return httpx.Response(200, content=wire_bytes(value))

    class Transport(httpx.MockTransport):
        def close(self) -> None:
            closed.append(True)
            super().close()

    try:
        result = posts.TikTokLinkedPosts(scope, contexts, Transport(wire), lambda: NOW).videos(
            identity, exclude_adsonly=False
        )
        assert len(result.pages) == 2 and len(calls) == 2 and closed == [True]
        assert result.observed_started_at == result.observed_ended_at == NOW
        assert result.expires_at <= NOW + timedelta(minutes=5)
        assert (
            result.publication_eligibility == "not_assessed" and result.spending_authority == "none"
        )
        assert result.coverage == "identity_video_view"
        assert result.request.owner.workspace_id == scope.workspace_id
        raw = result.model_dump_json()
        assert "12.123456789012345678901" in raw and "private-token" not in raw
        assert type(result).model_validate_json(raw) == result
    finally:
        contexts.close()


@pytest.mark.parametrize("change", ["revoke", "generation", "profile", "close", "foreign_scope"])
def test_actual_owned_change_discards_catalogue(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    encoded: Any,
    change: str,
) -> None:
    scope, contexts, alice = prepare(
        customer_engine, configuration, tmp_path, monkeypatch, replicas, encoded()
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
                assert session is not None
                session.revoked_at = int(time.time())
            else:
                source = db.scalar(
                    select(SourceConnection).where(SourceConnection.provider == "tiktok_ads")
                )
                assert source is not None
                source.generation += 1
            db.commit()

    def wire(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if change != "close":
            invalidate()  # Real separate DB transaction while HTTP executes, no held caller locks.
        return httpx.Response(200, content=wire_bytes(body()))

    class Transport(httpx.MockTransport):
        def close(self) -> None:
            closed.append(True)
            if change == "close":
                invalidate()
            super().close()

    if change == "foreign_scope":
        scope = scope.model_copy(update={"workspace_id": scope.workspace_id + 1000})
    try:
        with pytest.raises((TikTokDiscoveryUnavailable, HTTPException)):
            posts.TikTokLinkedPosts(scope, contexts, Transport(wire), lambda: NOW).videos(
                TikTokUserIdentityV1(identity_type="TT_USER", identity_id="linked-1"),
                exclude_adsonly=True,
            )
        assert len(calls) == (0 if change == "foreign_scope" else 1)
        assert closed == [True]
    finally:
        contexts.close()
