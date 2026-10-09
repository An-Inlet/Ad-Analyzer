"""Current source-only TikTok reads; controlled catalog and actual linked MockGET distinct."""

from pathlib import Path
from typing import Any, cast

import pytest
from app.settings import Settings
from sqlalchemy import Engine

from tests.test_campaign_video import encoded as encoded
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration
from tests.tiktok_current_read_fixture import configured_tiktok_customer
from tests.tiktok_draft_retained_fixture import retained_tiktok_draft_fixture
from tests.tiktok_linked_current_read_fixture import configured_linked_customer


@pytest.mark.planning_boundary
@pytest.mark.parametrize("linked", [False, True])
def test_current_tiktok_owned_read(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    encoded: Any,
    linked: bool,
) -> None:
    with retained_tiktok_draft_fixture(customer_engine, tmp_path / "retained", encoded()) as (
        engine,
        ids,
        media,
    ):
        clients = cast(Any, replicas).__wrapped__(engine, monkeypatch)
        try:
            build = configured_linked_customer if linked else configured_tiktok_customer
            alice, base, _, draft, revision, server, requests, control = build(
                engine, configuration, media, monkeypatch, clients, ids
            )
            denied = alice.post(base + "/mandates", json={}, headers=headers(alice))
            assert denied.status_code == 409
            assert denied.json()["detail"] == "advertising_writes_disabled_in_planning_mvp"
            endpoint = "/tiktok/linked/options" if linked else "/social/options"
            result = alice.post(
                base + endpoint,
                headers=headers(alice),
                json={
                    "draft_id": draft,
                    "draft_revision": revision,
                },
            )
            assert result.status_code == 200, result.text
            assert result.json()["options"]
            if linked:
                assert requests and all(r.method == "GET" for r in requests)
            else:
                assert requests == []
                assert "tiktok_native_catalog_parser_unverified" in result.json()["blockers"]
            assert control["opened"] == control["closed"] > 0
            assert server.posts == server.activations == 0
        finally:
            clients[0].close()
            clients[1].close()
