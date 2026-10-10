"""Frontend contract checks; genuine configured API/browser acceptance is separate."""

import subprocess

import pytest

from tests.test_customer_portal import portal_executable


def test_versioned_execution_handoff_frontend_contract() -> None:
    result = subprocess.run(
        [portal_executable("node"), "tests/javascript/initial_execution_contract.mjs"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("version", ["v1", "v2"])
def historical_contract_execution_ui_stale_results_and_separate_approval(version: str) -> None:
    result = subprocess.run(
        [portal_executable("node"), "tests/javascript/initial_execution_dom.mjs", version],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
