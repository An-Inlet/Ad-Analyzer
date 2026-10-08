"""Exact browser period input parsing; live controller acceptance is separate."""

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.planning_boundary


def test_exact_reporting_period_input_projection() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["node", "tests/javascript/plan_periods.mjs"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Exact reporting period controls passed" in result.stdout
