"""Reserved creative input gate; recognition does not activate a policy."""

from app.planning_documents.creative_basis import CreativeInputV1

CREATIVE_POLICY_VERSION = "inlet.descriptive-review.v5"
CREATIVE_GENERATOR_VERSION = "inlet.descriptive-planning.v5"


def validate_creative_policy(
    creative: CreativeInputV1 | None, policy_version: str, generator_version: str
) -> None:
    selected = (policy_version, generator_version) == (
        CREATIVE_POLICY_VERSION,
        CREATIVE_GENERATOR_VERSION,
    )
    if creative is not None:
        CreativeInputV1.model_validate(creative)
        if not selected:
            raise ValueError("typed creative inputs require an available creative policy")
    elif selected:
        raise ValueError("explicit typed creative inputs required")
