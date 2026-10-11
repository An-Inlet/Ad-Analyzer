"""Owner hypotheses are input-only until a versioned output consumer exists."""


def reject_google_budget_generation(value: object) -> None:
    if value is not None:
        raise ValueError("Google budget owner hypotheses are not supported in generated plans yet.")


def validate_google_budget_input_policy(value: object, version: str, generator: str) -> None:
    if value is not None and (version, generator) != (
        "inlet.descriptive-review.v5",
        "inlet.descriptive-planning.v5",
    ):
        raise ValueError("Google budget owner hypotheses require the configured private V5 policy.")
