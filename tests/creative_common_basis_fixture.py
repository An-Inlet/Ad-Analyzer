"""Exact Common Basis through owned APIs; no ready plans/proofs or image substitution."""

import hashlib
from dataclasses import dataclass
from datetime import date
from functools import partial
from pathlib import Path
from typing import Any, Literal

import pytest
from app.api import customer_campaign_review as media_api
from app.api import customer_planning_documents as planning
from app.campaign_review.storage import LocalMediaStore, get_media_store
from app.customers.access import SESSION_COOKIE
from app.planning_documents.creative_basis import (
    CreativeInputV1,
    CustomerListPriceV1,
    CustomerProductV1,
    PlanningMediaSelectionV1,
)
from app.planning_documents.creative_composition import canonical_creative_policy
from app.planning_documents.service import PlanningDocumentService
from app.settings import Settings
from sqlalchemy import Engine

from tests.q16_fixture import IMAGE, Q16Basis
from tests.selected_q01_q02_fixture import prepare_selected_common_basis
from tests.social_common_basis_fixture import prepare_social_common_basis
from tests.test_customer_optimization_api import headers

Platform = Literal["google_ads", "meta_ads", "tiktok_ads"]


@dataclass(frozen=True)
class CreativeCommonBasis:
    basis: Q16Basis
    body: dict[str, Any]
    calls: list[str]
    store: LocalMediaStore


def prepare_creative_common_basis(
    engine: Engine,
    config: Settings,
    replicas: Any,
    patch: pytest.MonkeyPatch,
    artifacts: Path,
    *,
    platform: Platform,
    selected_value: Literal["10", "0"] | None = None,
    missing_selected_day: date | None = None,
    configured_runtime: bool = False,
) -> CreativeCommonBasis:
    if platform != "google_ads" and selected_value is not None:
        raise ValueError("social fixtures cannot adopt Google selected observations")
    alice, bob, _ = replicas
    store = LocalMediaStore(artifacts)
    for client in (alice, bob):
        client.app.include_router(media_api.router)
        if not configured_runtime:
            client.app.dependency_overrides[get_media_store] = lambda: store
        else:
            assert get_media_store not in client.app.dependency_overrides
    original_session: list[str] = []

    def upload(wid: int) -> tuple[str, str]:
        original_session.append(alice.cookies[SESSION_COOKIE])
        raw = IMAGE.read_bytes()
        response = alice.post(
            f"/api/customer/v1/workspaces/{wid}/media",
            headers=headers(alice),
            content=raw,
        )
        assert response.status_code == 200, response.text
        value = response.json()
        assert value["sha256"] == hashlib.sha256(raw).hexdigest()
        assert value["mime"] == "image/png" and value["storage_mode"] == "private"
        return str(value["media_id"]), str(value["sha256"])

    if platform == "google_ads":
        basis, body, calls = prepare_selected_common_basis(
            engine,
            config,
            replicas,
            patch,
            artifacts,
            value=selected_value,
            missing_selected_day=missing_selected_day,
            owned_image_upload=upload,
            configure_planning=not configured_runtime,
        )
    else:
        basis, body, calls = prepare_social_common_basis(
            engine,
            config,
            replicas,
            patch,
            artifacts,
            platform=platform,
            owned_image_upload=upload,
            configure_planning=not configured_runtime,
        )
    assert original_session == [alice.cookies[SESSION_COOKIE]]
    body["inputs"]["creative"] = CreativeInputV1(
        product=CustomerProductV1(
            name="Reusable travel mug",
            list_price=CustomerListPriceV1(micros=25_000_000, currency="USD"),
            customer_asserted_facts=(),
            restrictions=("No approved health claims or testimonials.",),
        ),
        media_selections=(
            PlanningMediaSelectionV1(
                media_id=basis.media_id,
                expected_sha256=basis.media_sha256,
            ),
        ),
    ).model_dump(mode="json")
    if not configured_runtime:
        patch.setattr(
            planning,
            "PlanningDocumentService",
            partial(PlanningDocumentService, policy=canonical_creative_policy(), media_store=store),
        )
    return CreativeCommonBasis(basis, body, calls, store)
