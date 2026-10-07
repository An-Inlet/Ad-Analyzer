"""DOM contract acceptance; configured real API/browser evidence is separate."""

import subprocess

from tests.test_customer_portal import portal_executable


def test_initial_automation_stale_session_uncertainty_and_recovery() -> None:
    result = subprocess.run(
        [portal_executable("node"), "tests/javascript/initial_automation_dom.mjs"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
