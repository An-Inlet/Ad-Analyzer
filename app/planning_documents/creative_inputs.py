"""Reserved creative input gate; recognition does not activate a policy."""

from app.planning_documents.constraint_policy import is_constraint_policy
from app.planning_documents.creative_basis import CreativeInputV1
from app.planning_documents.owner_review_policy import is_owner_review_policy

CREATIVE_POLICY_VERSION = "inlet.descriptive-review.v5"
CREATIVE_GENERATOR_VERSION = "inlet.descriptive-planning.v5"


def validate_creative_policy(
    creative: CreativeInputV1 | None, policy_version: str, generator_version: str
) -> None:
    selected = (
        (policy_version, generator_version)
        == (
            CREATIVE_POLICY_VERSION,
            CREATIVE_GENERATOR_VERSION,
        )
        or is_owner_review_policy(policy_version, generator_version)
        or is_constraint_policy(policy_version, generator_version)
    )
    if creative is not None:
        CreativeInputV1.model_validate(creative)
        if not selected:
            raise ValueError("typed creative inputs require an available creative policy")
    elif selected:
        raise ValueError("explicit typed creative inputs required")
