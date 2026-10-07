"""Fresh-process contracts must not depend on prior application import ordering."""

import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "module",
    ["app.initial_planning.contracts", "app.publication.customer_optimization_contracts"],
)
def test_standalone_contract_import(module: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_customer_clock_reexport_identity() -> None:
    from app.publication.clock import utc_now
    from app.publication.customer_optimization_contracts import CustomerOptimizationRuntime
    from app.publication.customer_runtime import CustomerExecutionRuntime
    from app.publication.customer_runtime import utc_now as legacy

    assert legacy is utc_now
    assert CustomerOptimizationRuntime.__dataclass_fields__["clock"].default is utc_now
    assert CustomerExecutionRuntime.__dataclass_fields__["clock"].default is utc_now
