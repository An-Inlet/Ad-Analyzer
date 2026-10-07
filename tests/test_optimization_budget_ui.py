"""Intent/projection boundary for simple named optimization consent."""

import subprocess
from pathlib import Path

from tests.test_customer_portal import portal_executable


def test_exact_optimization_budget_browser_contract() -> None:
    node = portal_executable("node")
    result = subprocess.run(
        [node, "tests/javascript/optimization_budget_contract.mjs"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_optimization_page_has_customer_inputs_without_technical_authority() -> None:
    html = Path("app/portal/static/optimization.html").read_text()
    for removed in (
        "opt-starts",
        "opt-ends",
        "opt-actions",
        "opt-cooldown",
        "opt-per-plan",
        "opt-change",
    ):
        assert f'id="{removed}"' not in html
    assert 'id="opt-total"' in html and 'id="opt-aggressiveness"' in html
    assert 'value="conservative"' in html and 'value="balanced"' in html
    assert 'value="assertive"' in html
    assert 'id="opt-consent-check" type="checkbox">' in html
