"""Legacy generation refusal and explicit private owner-input admission."""


def reject_google_budget_generation(value: object) -> None:
    if value is not None:
        raise ValueError("Google budget owner hypotheses are not supported in generated plans yet.")


def validate_google_budget_input_policy(value: object, version: str, generator: str) -> None:
    if value is not None and (version, generator) not in (
        ("inlet.descriptive-review.v5", "inlet.descriptive-planning.v5"),
        ("inlet.descriptive-review.v6", "inlet.descriptive-planning.v6"),
    ):
        raise ValueError(
            "Google budget owner hypotheses require the configured private V5 or V6 policy."
        )
