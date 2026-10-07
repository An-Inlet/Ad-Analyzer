"""Separately pinned nonsecret policy; no execution runtime or hot reload authority."""

import hmac
import json
import re
from pathlib import Path

from app.initial_planning.budget_mandate_contracts import BudgetMandateOperatingPolicyV1
from app.planning_reporting.configuration import _unique_object

MAXIMUM_POLICY_BYTES = 32768


class BudgetMandateConfigurationError(ValueError):
    """Sanitized configuration error without file paths or payloads."""


def load_budget_mandate_policy(
    path: str | None, expected_digest: str | None
) -> BudgetMandateOperatingPolicyV1 | None:
    if path is None and expected_digest is None:
        return None
    if not path or not expected_digest or not re.fullmatch(r"[a-f0-9]{64}", expected_digest):
        raise BudgetMandateConfigurationError("budget_mandate_configuration_invalid")
    try:
        with Path(path).open("rb") as stream:
            payload = stream.read(MAXIMUM_POLICY_BYTES + 1)
        if len(payload) > MAXIMUM_POLICY_BYTES:
            raise ValueError("capacity")
        policy = BudgetMandateOperatingPolicyV1.model_validate(
            json.loads(payload, object_pairs_hook=_unique_object)
        )
        if not hmac.compare_digest(policy.digest(), expected_digest):
            raise ValueError("digest")
    except (OSError, ValueError, RecursionError):
        raise BudgetMandateConfigurationError("budget_mandate_configuration_invalid") from None
    return policy
