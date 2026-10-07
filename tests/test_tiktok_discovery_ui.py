"""Read-only display contracts; real configured API/TLS checks are separate."""

import subprocess

from tests.test_customer_portal import portal_executable


def test_tiktok_discovery_display_and_stale_response_guards() -> None:
    result = subprocess.run(
        [portal_executable("node"), "tests/javascript/tiktok_discovery_dom.mjs"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
