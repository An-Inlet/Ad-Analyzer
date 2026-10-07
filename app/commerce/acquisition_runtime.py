"""Explicit default-off read assembly; configuration never asserts source settlement."""

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.automation import AutomationControlKey, AutomationControlService, master_control_enabled
from app.commerce.acquisition_contracts import AcquisitionProfile
from app.commerce.independent_contracts import ScanUnavailable
from app.settings import Settings


def load_profile(configuration: Settings) -> AcquisitionProfile | None:
    if not configuration.customer_independent_acquisition_enabled:
        return None
    path = configuration.independent_acquisition_profile_path
    if not path:
        return None
    try:
        with Path(path).open("rb") as source:
            data = source.read(65537)
        if len(data) > 65536:
            raise ValueError("size")

        def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
            if len(items) != len(dict(items)):
                raise ValueError("duplicate")
            return dict(items)

        return AcquisitionProfile.model_validate(json.loads(data, object_pairs_hook=pairs))
    except (OSError, ValueError, ValidationError):
        raise ScanUnavailable("acquisition_configuration_unavailable") from None


def enabled(engine: Engine, configuration: Settings) -> bool:
    return configuration.customer_independent_acquisition_enabled and master_control_enabled(
        engine, AutomationControlKey.ALL_DATA_SYNCS
    )


def acquisition_transport(configuration: Settings) -> httpx.BaseTransport:
    if configuration.independent_acquisition_environment != "live":
        raise ScanUnavailable("acquisition_test_transport_required")
    return httpx.HTTPTransport(retries=0)


def utcnow() -> datetime:
    return datetime.now(UTC)


def require_owned_controls(
    db: Session, configuration: Settings, wid: int, environment: str
) -> None:
    controls = AutomationControlService(db)
    if (
        not configuration.customer_independent_acquisition_enabled
        or environment != configuration.independent_acquisition_environment
        or not controls.master_enabled(AutomationControlKey.ALL_DATA_SYNCS)
        or not controls.effective_enabled(wid, AutomationControlKey.SHOPIFY_SALES_SYNC)
    ):
        raise ScanUnavailable("acquisition_runtime_unavailable")
