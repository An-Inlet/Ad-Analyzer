"""Bounded local loader. Call once at startup; retain the returned frozen profile."""

import hmac
import json
import re
from pathlib import Path

from pydantic import ValidationError

from app.planning_reporting.contracts import PlanningReportingProfileV1

MAXIMUM_PROFILE_BYTES = 262144


class PlanningReportingConfigurationError(ValueError):
    """Sanitized error: never includes file content, location or validation payload."""


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def load_planning_reporting_profile(
    path: str | None, expected_digest: str | None
) -> PlanningReportingProfileV1 | None:
    """Absent pair disables assembly; any invalid configured pair fails closed.

    No cache, IO on import, environment lookup, defaults or hot reload. The process
    assembly owns retaining the exact returned profile for its API and worker.
    """
    if path is None and expected_digest is None:
        return None
    if not path or not expected_digest or not re.fullmatch(r"[a-f0-9]{64}", expected_digest):
        raise PlanningReportingConfigurationError("planning_reporting_configuration_invalid")
    try:
        with Path(path).open("rb") as stream:
            payload = stream.read(MAXIMUM_PROFILE_BYTES + 1)
        if len(payload) > MAXIMUM_PROFILE_BYTES:
            raise ValueError("capacity")
        value = json.loads(payload, object_pairs_hook=_unique_object)
        profile = PlanningReportingProfileV1.model_validate(value)
        if not hmac.compare_digest(profile.digest(), expected_digest):
            raise ValueError("digest")
    except (OSError, ValueError, RecursionError, ValidationError):
        raise PlanningReportingConfigurationError(
            "planning_reporting_configuration_invalid"
        ) from None
    return profile
