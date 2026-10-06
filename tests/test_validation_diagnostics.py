import shlex
import subprocess
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import pytest

from tests import test_automation_foundation as foundation
from tests.validation_diagnostics import MAX_FAILURES, MAX_REPORT_BYTES, nested_failure_summary


def report(path: Path, count: int = 2) -> None:
    suite = ET.Element("testsuite")
    for index in range(count):
        case = ET.SubElement(
            suite,
            "testcase",
            classname="tests.test_billing_browser_journey" if index == 0 else "tests.test_video",
            name=f"case{index}[sqlite]",
        )
        failure = ET.SubElement(case, "failure", message="exact failing condition")
        failure.text = "earlier-source " * 2000 + f"line{index}: final failing assertion"
    ET.ElementTree(suite).write(path)


def test_each_failure_survives_verbose_later_output_with_bounded_size(tmp_path: Path) -> None:
    path = tmp_path / "report.xml"
    report(path, MAX_FAILURES + 2)
    text = nested_failure_summary(path, "later video output" * 10000, "static details" * 10000)
    assert "tests.test_billing_browser_journey::case0[sqlite]" in text
    assert "line0: final failing assertion" in text
    assert "line7: final failing assertion" in text
    assert "Additional failures omitted: 2" in text
    assert len(text) < 27000


@pytest.mark.parametrize("kind", ["missing", "malformed", "oversized"])
def test_missing_or_bad_report_keeps_bounded_tool_failure(tmp_path: Path, kind: str) -> None:
    path = tmp_path / "report.xml"
    if kind == "malformed":
        path.write_text("not xml")
    if kind == "oversized":
        with path.open("wb") as file:
            file.truncate(MAX_REPORT_BYTES + 1)
    text = nested_failure_summary(path, "migration failed", "safe tool error")
    assert "JUnit evidence unavailable" in text
    assert "migration failed" in text and "safe tool error" in text


def test_nested_failure_still_fails_and_includes_original_test_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AD_ANALYZER_SKIP_NESTED_FULL_VALIDATION_REGRESSION", raising=False)
    monkeypatch.setattr(foundation, "disposable_postgres_env", lambda extra: dict(extra))
    calls = []

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        options = shlex.split(kwargs["env"]["PYTEST_ADDOPTS"])
        assert "--tb=short" in options
        path = Path(
            next(value.split("=", 1)[1] for value in options if value.startswith("--junitxml="))
        )
        report(path)
        assert kwargs["env"]["AD_ANALYZER_SKIP_NESTED_FULL_VALIDATION_REGRESSION"] == "true"
        return subprocess.CompletedProcess(command, 1, "later output" * 10000, "")

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(AssertionError, match="tests.test_billing_browser_journey::case0"):
        foundation.test_full_validation_can_run_twice_against_same_disposable_database(tmp_path)
    assert len(calls) == 1 and calls[0][-1] == "Full"


def test_success_still_runs_both_complete_validations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AD_ANALYZER_SKIP_NESTED_FULL_VALIDATION_REGRESSION", raising=False)
    monkeypatch.setattr(foundation, "disposable_postgres_env", lambda extra: dict(extra))
    reports = []

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert command[-1] == "Full"
        reports.append(kwargs["env"]["PYTEST_ADDOPTS"])
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)
    foundation.test_full_validation_can_run_twice_against_same_disposable_database(tmp_path)
    assert len(reports) == 2 and reports[0] != reports[1]
