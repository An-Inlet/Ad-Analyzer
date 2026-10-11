"""Pure-composed saved DTO and synthetic current UI; authenticated TLS is separate."""

from pathlib import Path

import pytest
from app.collectors.native_diagnostics import Inventory
from app.planning_catalog.metadata_contracts import PlanningMetadataV1, TargetCatalogV2
from app.planning_catalog.projection_v2 import project_v2

from tests import test_google_budget_owner_contracts as owner_contracts
from tests.owner_review_v6_fixture import ready
from tests.test_owner_review_v6_pure import compose
from tests.test_plan_target_picker import (
    test_target_picker_exact_choices_revocation_expiry_and_bounds as run_component,
)


def test_saved_owner_members_distinguish_duplicate_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def named_projection(
        inventory: Inventory, original_metadata: PlanningMetadataV1
    ) -> TargetCatalogV2:
        metadata = original_metadata.model_dump(mode="python")
        for entity in metadata["entities"]:
            if entity["kind"] == "campaign":
                entity["name"] = "Mug <img src=x>"
        return project_v2(inventory, PlanningMetadataV1.model_validate(metadata))

    monkeypatch.setattr(owner_contracts, "project_v2", named_projection)
    document = compose(ready())
    (tmp_path / "owner-duplicate-plan.json").write_text(document.model_dump_json())
    run_component(tmp_path, "plan_owner_duplicate_names_dom")
