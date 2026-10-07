"""Real network boundary; offline scenarios require explicit mock transport injection."""

import httpx
from fastapi import HTTPException

from app.production_runtime.optimization_contracts import OptimizationExecutionManifestV1


def optimization_execution_transport(
    manifest: OptimizationExecutionManifestV1,
) -> httpx.BaseTransport:
    if manifest.environment != "live" or not manifest.live_execution_enabled:
        raise HTTPException(409, "optimization_test_transport_required")
    return httpx.HTTPTransport(retries=0, trust_env=False)
