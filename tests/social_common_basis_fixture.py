"""Native social catalog-only Common Basis; no performance, video or execution seeded."""

import copy
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import httpx
import pytest
from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount
from app.api import customer_planning_documents as planning
from app.collectors import account_diagnostics
from app.meta.models import MetaConnection
from app.meta.security import Vault as MetaVault
from app.planning_documents.ports import PlanningCompositionPolicy
from app.planning_documents.service import PlanningDocumentService
from app.settings import Settings, settings
from app.sources.models import SourceConnection
from app.sources.security import SourceVault
from app.workspaces.models import WorkspaceIntegration
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.q16_fixture import Q16Basis, prepare_q16_basis
from tests.test_meta_native_inventory import PRIVATE
from tests.test_meta_native_inventory import Server as MetaServer
from tests.test_tiktok_native_inventory import Server as TikTokServer

Platform = Literal["meta_ads", "tiktok_ads"]


def social_account(
    engine: Engine,
    wid: int,
    patch: pytest.MonkeyPatch,
    calls: list[str],
    *,
    platform: Platform,
) -> int:
    """Exact owned fixture bootstrap; actual Vault/context/native HTTP readers follow."""
    patch.setattr(settings, "meta_token_encryption_key", SecretStr(Fernet.generate_key().decode()))
    patch.setattr(
        settings, "source_token_encryption_key", SecretStr(Fernet.generate_key().decode())
    )
    patch.setattr(settings, "meta_client_secret", SecretStr("synthetic-app-secret"))
    patch.setattr(settings, "customer_native_diagnostics_enabled", True)
    now = datetime.now(UTC)
    bundle = dict(access_token=PRIVATE, expires_at=(now + timedelta(hours=1)).isoformat())
    with Session(engine) as db:
        integration = WorkspaceIntegration(
            workspace_id=wid,
            integration_key="common-" + platform,
            provider=platform,
            display_name="Mug " + platform,
            status="active",
            configuration={},
        )
        db.add(integration)
        db.flush()
        account = AdvertisingAccount(
            workspace_id=wid,
            connection_id=integration.id,
            platform=AdvertisingPlatform(platform),
            external_account_id="123",
            name="Mug " + platform,
            currency_code="USD",
            time_zone="America/New_York",
        )
        db.add(account)
        db.flush()
        if platform == "meta_ads":
            db.add(
                MetaConnection(
                    workspace_id=wid,
                    workspace_integration_id=integration.id,
                    account_id=account.id,
                    external_account_id="123",
                    encrypted_credentials=MetaVault(settings).seal(wid, "123", bundle),
                    conversion_action_type="purchase",
                )
            )
        else:
            sid = uuid4().hex
            db.add(
                SourceConnection(
                    id=sid,
                    workspace_id=wid,
                    integration_id=integration.id,
                    account_id=account.id,
                    provider=platform,
                    external_id="123",
                    status="connected",
                    generation=1,
                    window_start=date(2026, 8, 1),
                    window_end=date(2026, 9, 30),
                    encrypted_grant=SourceVault().seal(wid, platform, sid, bundle),
                )
            )
        db.commit()
        aid = account.id
    meta = MetaServer()
    meta.account["timezone_name"] = "America/New_York"
    meta.campaigns.append({**meta.campaigns[0], "id": "7"})
    meta.adsets.append({**meta.adsets[0], "id": "8", "campaign_id": "7"})
    tiktok = TikTokServer()

    def wire(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        assert request.method == "GET"
        if platform == "meta_ads":
            fields = request.url.params.get("fields", "").split(",")
            if "name" in fields:
                rows = copy.deepcopy(
                    meta.adsets if request.url.path.endswith("adsets") else meta.campaigns
                )
                for row in rows:
                    row["name"] = (
                        "Mug " + ("Ad Set " if "campaign_id" in row else "Campaign ") + row["id"]
                    )
                return httpx.Response(200, json={"data": rows})
            return meta(request)
        response = tiktok(request)
        body = response.json()
        for row in body["data"]["list"]:
            if "currency" in row:
                row["timezone"] = "America/New_York"
            elif "adgroup_id" in row:
                row["adgroup_name"] = "Mug Ad Group"
            else:
                row["campaign_name"] = "Mug Campaign"
        return httpx.Response(response.status_code, json=body)

    patch.setattr(account_diagnostics, "diagnostic_transport", lambda: httpx.MockTransport(wire))
    return aid


def prepare_social_common_basis(
    engine: Engine,
    config: Settings,
    replicas: Any,
    patch: pytest.MonkeyPatch,
    artifacts: Path,
    *,
    platform: Platform,
    owned_image_upload: Callable[[int], tuple[str, str]] | None = None,
) -> tuple[Q16Basis, dict[str, Any], list[str]]:
    calls: list[str] = []
    basis = prepare_q16_basis(
        engine,
        config,
        replicas,
        patch,
        artifacts,
        branch="privacy",
        native_calls=calls,
        generation_stage="october",
        owned_image_upload=owned_image_upload,
        native_account_factory=partial(social_account, platform=platform),
    )
    patch.setattr(
        planning,
        "PlanningDocumentService",
        partial(
            PlanningDocumentService,
            policy=PlanningCompositionPolicy(
                version="inlet.descriptive-review.v4",
                generator_version="inlet.descriptive-planning.v4",
            ),
        ),
    )
    basis.body["inputs"]["selected_reporting"] = []
    return basis, basis.body, calls
