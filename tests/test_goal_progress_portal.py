"""Focused rendering contracts; actual API/TLS journey is verified separately."""

import subprocess

from tests.test_customer_portal import portal_executable


def test_goal_progress_rendering_contracts() -> None:
    subprocess.run(
        [portal_executable("node"), "--test", "tests/javascript/goal_progress.test.mjs"],
        check=True,
    )
