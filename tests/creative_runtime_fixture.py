"""Actual owned API sources and uploads; only server configuration/MockHTTP injected."""

import io
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from app.api import customer_campaign_review as media_api
from app.api import customer_planning_documents as api
from app.campaign_review.storage import LocalMediaStore, get_media_store
from app.planning_documents.creative_basis import (
    CreativeInputV1,
    CustomerListPriceV1,
    CustomerProductV1,
    PlanningMediaSelectionV1,
)
from app.planning_documents.creative_composition import canonical_creative_policy
from app.planning_documents.service import PlanningDocumentService
from app.settings import Settings
from PIL import Image
from sqlalchemy import Engine

from tests.test_customer_optimization_api import headers
from tests.test_planning_documents_api import create_body
from tests.test_planning_evidence_adapter import setup_evidence
from tests.test_selected_runtime_api import configured as selected_configured


def configured(
    engine: Engine,
    config: Settings,
    replicas: Any,
    patch: pytest.MonkeyPatch,
    path: Path,
    *,
    platform: str = "google_ads",
    images: int = 1,
) -> Any:
    if platform == "google_ads":
        f, root, body, calls, reader = selected_configured(engine, config, replicas, patch)
    else:
        reader, ticket, principal, calls = setup_evidence(engine, config, replicas, patch, platform)
        f = SimpleNamespace(
            alice=replicas[0],
            bob=replicas[1],
            provider=replicas[2],
            wid=ticket.inputs.workspace_id,
            actor=principal.user.id,
            sid=principal.session.digest,
            aid=ticket.inputs.accounts[0].account_id,
            calls=[],
        )
        root = f"/api/customer/v1/workspaces/{f.wid}/planning/plans"
        body = create_body(ticket.inputs)
        body["inputs"]["selected_reporting"] = []
        for client in (f.alice, f.bob):
            client.app.include_router(api.router)
    store = LocalMediaStore(path)
    # Actual upload endpoint and private store. Byte decoding/ownership remain real.
    for client in (f.alice, f.bob):
        client.app.include_router(media_api.router)
        client.app.dependency_overrides[get_media_store] = lambda: store
    selections = []
    for index in range(images):
        stream = io.BytesIO()
        Image.new("RGB", (4, 4), (index, 100, 0)).save(stream, "PNG")
        response = f.alice.post(
            f"/api/customer/v1/workspaces/{f.wid}/media",
            headers=headers(f.alice),
            content=stream.getvalue(),
        )
        assert response.status_code == 200, response.text
        selected = response.json()
        selections.append(
            PlanningMediaSelectionV1(
                media_id=selected["media_id"],
                expected_sha256=selected["sha256"],
            )
        )
    creative = CreativeInputV1(
        product=CustomerProductV1(
            name="Inlet Test Mug",
            list_price=CustomerListPriceV1(micros=24_000_000, currency="USD"),
            customer_asserted_facts=("Reusable ceramic mug",),
            restrictions=("Do not claim dishwasher safety",),
        ),
        media_selections=tuple(selections),
    )
    body["inputs"]["creative"] = creative.model_dump(mode="json")
    body["inputs"]["product_offer"] = "Inlet Test Mug, USD 24 customer-supplied price"
    patch.setattr(
        api,
        "PlanningDocumentService",
        partial(
            PlanningDocumentService,
            policy=canonical_creative_policy(),
            media_store=store,
        ),
    )
    return f, root, body, calls, reader, store
