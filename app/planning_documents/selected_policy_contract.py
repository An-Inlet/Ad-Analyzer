"""Exact selected policy recognition; no runtime registration or authority."""

from typing import TYPE_CHECKING, Literal

from pydantic import Field, model_validator

from app.planning_documents.common import Frozen

if TYPE_CHECKING:
    from app.planning_documents.ports import PlanningCompositionPolicy


class SelectedPolicyContractV1(Frozen):
    policy_version: str = Field(strict=True)
    generator_version: str = Field(strict=True)
    requires_creative: bool = Field(strict=True)
    reporting_witness_kind: Literal["local_reporting_v3"] = "local_reporting_v3"

    @model_validator(mode="after")
    def exact(self) -> "SelectedPolicyContractV1":
        if (self.policy_version, self.generator_version, self.requires_creative) not in (
            ("inlet.descriptive-review.v4", "inlet.descriptive-planning.v4", False),
            ("inlet.descriptive-review.v5", "inlet.descriptive-planning.v5", True),
            ("inlet.descriptive-review.v6", "inlet.descriptive-planning.v6", True),
        ):
            raise ValueError("exact selected policy descriptor required")
        return self

    @property
    def requires_owner_review(self) -> bool:
        return self.policy_version == "inlet.descriptive-review.v6"


def selected_policy_contract(
    policy_version: str, generator_version: str
) -> SelectedPolicyContractV1:
    if type(policy_version) is not str or type(generator_version) is not str:
        raise ValueError("exact policy version strings required")
    return SelectedPolicyContractV1(
        policy_version=policy_version,
        generator_version=generator_version,
        requires_creative=policy_version
        in ("inlet.descriptive-review.v5", "inlet.descriptive-review.v6"),
    )


def assert_selected_ticket_policy(
    policy_version: str, policy_digest: str
) -> SelectedPolicyContractV1:
    from app.planning_documents.ports import PlanningCompositionPolicy

    if type(policy_version) is not str or type(policy_digest) is not str:
        raise ValueError("exact policy version and digest strings required")
    for version in (4, 5, 6):
        policy = PlanningCompositionPolicy(
            version=f"inlet.descriptive-review.v{version}",
            generator_version=f"inlet.descriptive-planning.v{version}",
        )
        if (policy_version, policy_digest) == (policy.version, policy.digest()):
            return selected_policy_contract(policy.version, policy.generator_version)
    raise ValueError("exact canonical selected ticket policy required")


def assert_selected_composition_policy(
    policy: "PlanningCompositionPolicy",
    *,
    ticket_policy_version: str,
    ticket_policy_digest: str,
) -> SelectedPolicyContractV1:
    from app.planning_documents.ports import PlanningCompositionPolicy

    policy = PlanningCompositionPolicy.model_validate(policy)
    contract = assert_selected_ticket_policy(ticket_policy_version, ticket_policy_digest)
    canonical = PlanningCompositionPolicy(
        version=contract.policy_version, generator_version=contract.generator_version
    )
    if policy != canonical or policy.digest() != ticket_policy_digest:
        raise ValueError("exact canonical composition and ticket binding required")
    return contract
