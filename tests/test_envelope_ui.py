import subprocess

from tests.test_customer_portal import portal_executable


def test_envelope_contract_rendering_and_stale_responses() -> None:
    result = subprocess.run(
        [portal_executable("node"), "tests/javascript/envelope_ui_dom.mjs"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
