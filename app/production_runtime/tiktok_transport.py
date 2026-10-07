"""Explicit real-network boundary; scenario sources require a test transport seam."""

import httpx
from fastapi import HTTPException

from app.production_runtime.tiktok_contracts import TikTokExecutionManifestV1


def tiktok_execution_transport(manifest: TikTokExecutionManifestV1) -> httpx.BaseTransport:
    if manifest.environment != "live" or not manifest.live_execution_enabled:
        raise HTTPException(409, "tiktok_execution_test_transport_required")
    return httpx.HTTPTransport(retries=0, trust_env=False)
