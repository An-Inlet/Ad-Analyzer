"""Job-boundary guards keep manual diagnostics out of paid Full validation."""

import ast
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[1]


def workflow() -> dict[str, Any]:
    return dict(yaml.load((ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader))


def enabled(expression: str, event: str, mode: str) -> bool:
    text = expression.replace("github.event_name", "event").replace("inputs.mode", "mode")
    text = text.replace("&&", "and").replace("||", "or")

    def value(node: ast.AST) -> Any:
        if isinstance(node, ast.Name):
            return {"event": event, "mode": mode}[node.id]
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.BoolOp):
            values = [value(item) for item in node.values]
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            left, right = value(node.left), value(node.comparators[0])
            # GitHub expression equality ignores string case.
            if isinstance(left, str) and isinstance(right, str):
                left, right = left.casefold(), right.casefold()
            if isinstance(node.ops[0], ast.Eq):
                return left == right
            if isinstance(node.ops[0], ast.NotEq):
                return left != right
        raise AssertionError("Unexpected job-condition syntax requires explicit review")

    return bool(value(ast.parse(text, mode="eval").body))


@pytest.mark.parametrize("event,mode,expected", [
    ("push", "", {"validation"}),
    ("pull_request", "", {"validation"}),
    ("pull_request", "browser-startup", {"validation"}),
    ("workflow_dispatch", "full", {"validation"}),
    ("workflow_dispatch", "browser-startup", {"browser-startup"}),
    ("workflow_dispatch", "", set()),
    ("workflow_dispatch", "unknown", set()),
    ("workflow_dispatch", "FULL", {"validation"}),
    ("workflow_dispatch", "BROWSER-STARTUP", {"browser-startup"}),
    ("workflow_dispatch", "browser-startup ", set()),
])
def test_job_selection_has_no_diagnostic_fallback_to_full(
    event: str, mode: str, expected: set[str]
) -> None:
    jobs = workflow()["jobs"]
    assert {name for name, job in jobs.items() if enabled(job["if"], event, mode)} == expected


def test_manual_input_and_diagnostic_job_are_bounded_and_pinned() -> None:
    document = workflow()
    mode = document["on"]["workflow_dispatch"]["inputs"]["mode"]
    assert mode["type"] == "choice" and mode["required"] == "true"
    assert mode["default"] == "full" and mode["options"] == ["full", "browser-startup"]
    job = document["jobs"]["browser-startup"]
    assert job["timeout-minutes"] == "5"
    assert not {"services", "env", "needs", "strategy"} & job.keys()
    assert document["permissions"] == {"contents": "read"}
    checkout, collect = job["steps"]
    assert checkout["uses"] == "actions/checkout@11d5960a326750d5838078e36cf38b85af677262"
    assert checkout["with"] == {
        "ref": "c845ccaf30c71d0b707b73cc93a99023111720ba",
        "persist-credentials": "false", "fetch-depth": "1",
    }
    assert collect["run"] == "python3 -m scripts.diagnose_browser_startup"
    assert collect["timeout-minutes"] == "2"
    assert "uses" not in collect
