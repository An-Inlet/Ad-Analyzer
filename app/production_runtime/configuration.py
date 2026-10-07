"""Bounded nonsecret Google execution manifest; never executable proof/source code."""

import hmac
import json
import re
from pathlib import Path

from app.planning_reporting.configuration import _unique_object
from app.production_runtime.contracts import GoogleExecutionManifestV1

MAXIMUM_MANIFEST_BYTES = 16384


class GoogleRuntimeConfigurationError(ValueError):
    """Sanitized parse error without paths, credentials or configuration payloads."""


def load_google_execution_manifest(
    path: str | None, expected_digest: str | None
) -> GoogleExecutionManifestV1 | None:
    if path is None and expected_digest is None:
        return None
    if not path or not expected_digest or not re.fullmatch(r"[a-f0-9]{64}", expected_digest):
        raise GoogleRuntimeConfigurationError("google_execution_configuration_invalid")
    try:
        with Path(path).open("rb") as stream:
            payload = stream.read(MAXIMUM_MANIFEST_BYTES + 1)
        if len(payload) > MAXIMUM_MANIFEST_BYTES:
            raise ValueError("capacity")
        manifest = GoogleExecutionManifestV1.model_validate(
            json.loads(payload, object_pairs_hook=_unique_object)
        )
        if not hmac.compare_digest(manifest.digest(), expected_digest):
            raise ValueError("digest")
    except (OSError, ValueError, RecursionError):
        raise GoogleRuntimeConfigurationError("google_execution_configuration_invalid") from None
    return manifest
