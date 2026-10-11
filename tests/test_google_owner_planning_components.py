"""V6 component intent/proof boundary; authenticated service journeys are separate."""

from pathlib import Path

from tests.test_plan_target_picker import (
    test_target_picker_exact_choices_revocation_expiry_and_bounds as run_component,
)


def test_owner_review_intents_history_and_context_fences(tmp_path: Path) -> None:
    run_component(tmp_path, "plan_google_owner_inputs_dom")
