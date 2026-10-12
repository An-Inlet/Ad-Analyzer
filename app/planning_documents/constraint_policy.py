"""Candidate policy identity; Settings/runtime selection deliberately remain unchanged."""

CONSTRAINT_POLICY_VERSION = "inlet.descriptive-review.v7"
CONSTRAINT_GENERATOR_VERSION = "inlet.descriptive-planning.v7"


def is_constraint_policy(version: object, generator: object) -> bool:
    return (version, generator) == (CONSTRAINT_POLICY_VERSION, CONSTRAINT_GENERATOR_VERSION)
