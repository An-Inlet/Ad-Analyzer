"""Real renderer using genuine pure-composed V5/V6 DTOs; no authenticated API claim."""

import shutil
from pathlib import Path

from tests.owner_review_v6_fixture import ready as ready_v6
from tests.test_creative_plan_composer import compose as compose_v5
from tests.test_creative_plan_composer import ready as ready_v5
from tests.test_owner_review_v6_pure import compose as compose_v6
from tests.test_plan_target_picker import (
    test_target_picker_exact_choices_revocation_expiry_and_bounds as run_component,
)


def test_saved_creative_policy_accepts_exact_v5_v6_and_refuses_mixed(tmp_path: Path) -> None:
    for version, document in (
        ("5", compose_v5(ready_v5())),
        ("6", compose_v6(ready_v6())),
        ("6-empty", compose_v6(ready_v6(empty=True))),
    ):
        (tmp_path / f"creative-v{version}.json").write_text(document.model_dump_json())
    shutil.copy("app/portal/static/plan-document.mjs", tmp_path / "plan-document.mjs")
    shutil.copy("app/portal/static/plan-constraints.mjs", tmp_path / "plan-constraints.mjs")
    shutil.copy(
        "app/portal/static/plan-reporting-comparability.mjs",
        tmp_path / "plan-reporting-comparability.mjs",
    )
    run_component(tmp_path, "plan_google_owner_creative_policy_dom")
