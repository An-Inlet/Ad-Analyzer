"""Exact customer rule projection and explicit Start contract; not live evidence."""

import subprocess

import pytest

from tests.test_customer_portal import portal_executable


@pytest.mark.parametrize("script", ["reported_rule_view.mjs", "optimization_session_fence.mjs"])
def test_reported_rule_customer_view_and_start(script: str) -> None:
    result = subprocess.run(
        [portal_executable("node"), f"tests/javascript/{script}"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
