"""Small no-database checks for the closed private browser fixture state machine."""

from typing import Any

import pytest

from tests.planning_target_inventory_fixture import InventoryScenario, Platform


@pytest.mark.parametrize("platform", ["google_ads", "meta_ads", "tiktok_ads"])
def test_inventory_phases_cannot_skip_replay_or_reset(platform: Platform) -> None:
    scenario = InventoryScenario(platform)
    with pytest.raises(ValueError, match="ordered"):
        scenario.advance("replacement")
    assert str(scenario.phase) == "original"
    scenario.advance("absent")
    with pytest.raises(ValueError, match="ordered"):
        scenario.advance("absent")
    scenario.advance("replacement")
    for invalid in ("absent", "replacement", "original", "arbitrary"):
        phase: Any = invalid
        with pytest.raises(ValueError, match="ordered"):
            scenario.advance(phase)
    assert scenario.phase == "replacement"


@pytest.mark.parametrize("platform", ["unknown", "", None])
def test_inventory_platform_is_closed(platform: Any) -> None:
    with pytest.raises(ValueError, match="unsupported"):
        InventoryScenario(platform)
