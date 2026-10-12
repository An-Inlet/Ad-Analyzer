"""Synthetic topology transitions through real native HTTP readers, never catalogs."""

import json
from typing import Literal, cast

import httpx
import pytest
from app.collectors import account_diagnostics
from sqlalchemy import Engine, Table

from tests.planning_target_inventory_fixture import Platform


class UnknownParentScenario:
    def __init__(self, platform: Platform) -> None:
        self.platform = platform
        self.phase: Literal["original", "orphan", "recovered"] = "original"
        self._transport = account_diagnostics.diagnostic_transport

    def advance(self, phase: Literal["orphan", "recovered"]) -> None:
        if (self.phase, phase) not in (("original", "orphan"), ("orphan", "recovered")):
            raise ValueError("ordered topology phase required")
        self.phase = phase

    def wire(self, request: httpx.Request) -> httpx.Response:
        phase = self.phase
        transport = self._transport()
        assert transport is not None
        with transport:
            response = transport.handle_request(request)
            response.read()
        payload = response.json()
        if self.platform == "google_ads" and "results" in payload:
            query = json.loads(request.content)["query"]
            if "FROM ad_group" in query:
                parent = "1" if phase == "original" else "9"
                payload["results"] = [{"adGroup": dict(
                    resourceName="customers/1234567890/adGroups/7",
                    campaign=f"customers/1234567890/campaigns/{parent}",
                    name="Owned Child", status="ENABLED", type="SEARCH_STANDARD",
                )}]
            elif phase == "recovered":
                for row in payload["results"]:
                    if "campaign" in row:
                        row["campaign"]["resourceName"] = "customers/1234567890/campaigns/9"
        elif self.platform == "meta_ads" and request.url.path.endswith(("/campaigns", "/adsets")):
            for row in payload["data"]:
                if "campaign_id" in row and phase != "original":
                    row["campaign_id"] = "9"
                elif "campaign_id" not in row and phase == "recovered":
                    row["id"] = "9"
        elif self.platform == "tiktok_ads" and request.url.path.endswith(
            ("/campaign/get/", "/adgroup/get/")
        ):
            for row in payload["data"]["list"]:
                if phase == "recovered" or (
                    phase == "orphan" and request.url.path.endswith("/adgroup/get/")
                ):
                    row["campaign_id"] = "9"
        return httpx.Response(response.status_code, json=payload)


def install_unknown_parent_scenario(
    platform: Platform, patch: pytest.MonkeyPatch
) -> UnknownParentScenario:
    scenario = UnknownParentScenario(platform)
    patch.setattr(
        account_diagnostics, "diagnostic_transport", lambda: httpx.MockTransport(scenario.wire)
    )
    return scenario


def topology_state(engine: Engine) -> dict[str, dict[str, int | str]]:
    """Read-only fingerprints of every planning and catalog graph row; no auth data."""
    from hashlib import sha256

    from app.planning_documents.catalog_receipt_models import (
        CatalogReceiptRow,
        CatalogReceiptSelectionRow,
        InputCatalogReceiptRow,
    )
    from app.planning_documents.models import (
        PlanDependencyRow,
        PlanEventRow,
        PlanInputRow,
        PlanRequestRow,
        PlanRow,
        PlanVersionRow,
    )
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    result: dict[str, dict[str, int | str]] = {}
    with Session(engine) as db:
        for model in (
            PlanRow, PlanInputRow, PlanVersionRow, PlanDependencyRow, PlanEventRow,
            PlanRequestRow, CatalogReceiptRow, CatalogReceiptSelectionRow, InputCatalogReceiptRow,
        ):
            table = cast(Table, model.__table__)
            rows = db.execute(select(table).order_by(*table.primary_key.columns)).mappings().all()
            raw = json.dumps([dict(row) for row in rows], sort_keys=True, default=str)
            result[table.name] = {"count": len(rows), "sha256": sha256(raw.encode()).hexdigest()}
    return result
