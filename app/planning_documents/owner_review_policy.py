"""Reserved pure owner-review policy identity; not a runtime capability."""

OWNER_REVIEW_POLICY_VERSION = "inlet.descriptive-review.v6"
OWNER_REVIEW_GENERATOR_VERSION = "inlet.descriptive-planning.v6"


def is_owner_review_policy(version: object, generator: object) -> bool:
    return (version, generator) == (OWNER_REVIEW_POLICY_VERSION, OWNER_REVIEW_GENERATOR_VERSION)
