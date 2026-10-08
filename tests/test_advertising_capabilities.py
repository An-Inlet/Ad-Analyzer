"""The deployed planning artifact cannot gain writes from execution configuration."""

import pytest
from app.advertising_capabilities import (
    AdvertisingWritesDisabled,
    advertising_writes_enabled,
    require_advertising_write,
)


@pytest.mark.parametrize("value", ["true", "1", "live", "execution"])
def test_environment_cannot_enable_advertising_writes(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    for name in (
        "INLET_ADVERTISING_WRITES_ENABLED",
        "AD_ANALYZER_CUSTOMER_SESSION_AUTOMATION_ENABLED",
        "AD_ANALYZER_GOOGLE_ADS_LIVE_EXECUTION_ENABLED",
    ):
        monkeypatch.setenv(name, value)
    assert advertising_writes_enabled() is False
    with pytest.raises(AdvertisingWritesDisabled) as denied:
        require_advertising_write()
    assert denied.value.status_code == 409
    assert denied.value.detail == "advertising_writes_disabled_in_planning_mvp"
