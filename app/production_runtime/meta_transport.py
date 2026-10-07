"""Explicit real-network boundary; scenario sources require a test transport seam."""

import httpx
from fastapi import HTTPException

from app.production_runtime.meta_contracts import MetaExecutionManifestV1


def meta_execution_transport(manifest: MetaExecutionManifestV1) -> httpx.BaseTransport:
    if manifest.environment != "live" or not manifest.live_execution_enabled:
        raise HTTPException(409, "meta_execution_test_transport_required")
    return httpx.HTTPTransport(retries=0, trust_env=False)
