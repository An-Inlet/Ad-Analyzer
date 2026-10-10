"""Detached current rule-module DOM units; not customer-page or live API evidence."""

import hashlib
import subprocess
from pathlib import Path

import pytest

from tests.test_customer_portal import portal_executable


@pytest.mark.parametrize("script", ["reported_rule_view.mjs", "optimization_session_fence.mjs"])
def test_reported_rule_customer_view_and_start(script: str) -> None:
    assert hashlib.sha256(
        Path("tests/fixtures/retained-optimization-dom.html").read_bytes()
    ).hexdigest() == "bc59f179bc8a32ce6003581946c13dc3b4a5b7c5b42cd0a82e9d9d07b848f09e"
    result = subprocess.run(
        [portal_executable("node"), f"tests/javascript/{script}"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
