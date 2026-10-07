"""Intent-only frontend and stale output handling; actual TLS is separate."""

import subprocess

from tests.test_customer_portal import portal_executable


def test_candidate_read_frontend_contract() -> None:
    result = subprocess.run(
        [portal_executable("node"), "tests/javascript/candidate_read_dom.mjs"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
