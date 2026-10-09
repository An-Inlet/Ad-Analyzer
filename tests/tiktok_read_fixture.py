"""Current owned TikTok read setup; no legacy approval or execution authority."""

import json
from collections.abc import Generator
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from app.advertising_capabilities import advertising_writes_enabled
from app.mandates.models import Mandate
from app.production_runtime import assembly
from app.production_runtime.tiktok_configuration import TikTokConfigurationBundleV1
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionConsent,
    ProviderExecutionMandate,
    ProviderExecutionReceipt,
    ProviderExecutionResponse,
    ProviderExecutionReview,
    ProviderExposureReservation,
)
from app.settings import Settings, settings
from app.sources.models import SourceConnection
from app.sources.security import SourceVault
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import login
from tests.test_planning_target_catalog_api import seed
from tests.test_tiktok_runtime_contracts import bundle_document, manifest


@dataclass(frozen=True)
class TikTokReadIds:
    workspace_id: int
    account_id: int
    actor_id: str
    source_id: str


def assert_no_advertising_authority(engine: Engine) -> None:
    assert advertising_writes_enabled() is False
    with Session(engine) as db:
        for model in (
            Mandate,
            ProviderExecutionMandate,
            ProviderExecutionConsent,
            ProviderExecutionAttempt,
            ProviderExecutionReview,
            ProviderExecutionResponse,
            ProviderExecutionReceipt,
            ProviderExposureReservation,
        ):
            assert db.scalar(select(func.count()).select_from(model)) == 0, model.__tablename__


@pytest.fixture
def read_only_graph(customer_engine: Engine) -> Generator[None, None, None]:
    assert_no_advertising_authority(customer_engine)
    yield
    assert_no_advertising_authority(customer_engine)


def prepare_tiktok_read_source(
    engine: Engine,
    configuration: Settings,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> TikTokReadIds:
    assert_no_advertising_authority(engine)
    monkeypatch.setattr(
        settings, "source_token_encryption_key", SecretStr(Fernet.generate_key().decode())
    )
    owned = seed(engine, configuration, path, "tiktok_ads")
    with Session(engine) as db:
        source = db.scalar(
            select(SourceConnection).where(
                SourceConnection.workspace_id == owned.workspace_id,
                SourceConnection.account_id == owned.account_id,
                SourceConnection.provider == "tiktok_ads",
            )
        )
        assert source is not None
        # Match the original read contract's synthetic grant and ordinary lifetime.
        source.encrypted_grant = SourceVault().seal(
            owned.workspace_id,
            "tiktok_ads",
            source.id,
            {
                "access_token": "offline-tiktok-access",
                "expires_at": (NOW + timedelta(hours=2)).isoformat(),
            },
        )
        db.commit()
        ids = TikTokReadIds(owned.workspace_id, owned.account_id, owned.actor, source.id)
    document = bundle_document()
    selected = manifest(TikTokConfigurationBundleV1.from_document(document))
    mp, bp = path / "tiktok-read-manifest.json", path / "tiktok-read-bundle.json"
    mp.write_text(selected.model_dump_json())
    bp.write_text(json.dumps(document))
    monkeypatch.setattr(settings, "tiktok_execution_manifest_path", str(mp))
    monkeypatch.setattr(settings, "tiktok_execution_manifest_digest", selected.digest())
    monkeypatch.setattr(settings, "tiktok_execution_bundle_path", str(bp))
    monkeypatch.setattr(assembly, "execution_clock", lambda: NOW)
    assert login(replicas[0], "diagnostic-owner:read") == ids.actor_id
    assert_no_advertising_authority(engine)
    return ids
