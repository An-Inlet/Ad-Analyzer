"""Closed private reporting contracts. Recognition does not enable runtime policy."""

from typing import Literal

from app.planning_documents.common import Frozen
from app.planning_documents.ports import PlanningCompositionPolicy


class ReportingCapability(Frozen):
    mode: Literal[
        "legacy_exact_window",
        "presence_exact_window",
        "presence_requested_window",
        "selected_requested_window",
    ]
    local_witness_kind: Literal["local_reporting_v1", "local_reporting_v2", "local_reporting_v3"]


def reporting_capability(policy_version: str, generator_version: str) -> ReportingCapability:
    if type(policy_version) is not str or type(generator_version) is not str:
        raise ValueError("exact policy version strings required")
    for version, mode, witness in (
        (1, "legacy_exact_window", "local_reporting_v1"),
        (2, "presence_exact_window", "local_reporting_v2"),
        (3, "presence_requested_window", "local_reporting_v2"),
        (4, "selected_requested_window", "local_reporting_v3"),
    ):
        if (policy_version, generator_version) == (
            f"inlet.descriptive-review.v{version}",
            f"inlet.descriptive-planning.v{version}",
        ):
            return ReportingCapability.model_validate(dict(mode=mode, local_witness_kind=witness))
    raise ValueError("unknown or mixed reporting policy pair")


def ticket_reporting_capability(policy_version: str, policy_digest: str) -> ReportingCapability:
    if type(policy_version) is not str or type(policy_digest) is not str:
        raise ValueError("exact policy version and digest required")
    for version in (1, 2, 3, 4):
        policy = PlanningCompositionPolicy(
            version=f"inlet.descriptive-review.v{version}",
            generator_version=f"inlet.descriptive-planning.v{version}",
        )
        if policy.version == policy_version and policy.digest() == policy_digest:
            return reporting_capability(policy.version, policy.generator_version)
    raise ValueError("unknown or altered canonical reporting policy")
