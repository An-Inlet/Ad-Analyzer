"""Synthetic launch failures remain actionable and cannot qualify a browser."""

from pathlib import Path

import pytest
from scripts.check_browser_media import probe


def test_probe_reports_early_browser_exit(tmp_path: Path) -> None:
    browser = tmp_path / "browser"
    browser.write_text("#!/bin/sh\necho synthetic-startup-failure >&2\nexit 23\n")
    browser.chmod(0o700)
    result = probe(str(browser), {"/silent": b"", "/aac": b""}, tmp_path / "profile")
    assert result[0]["event"] == "browser_no_result"
    assert result[0]["exit_code"] == 23
    assert result[0]["requests"] == {}
    assert "synthetic-startup-failure" in result[0]["stderr"]


def test_probe_stderr_is_bounded_and_child_environment_is_filtered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("INLET_SYNTHETIC_SECRET", "must-not-inherit")
    browser = tmp_path / "browser"
    browser.write_text(
        '#!/bin/sh\nif [ -n "$INLET_SYNTHETIC_SECRET" ]; then exit 99; fi\n'
        'i=0\nwhile [ "$i" -lt 100 ]; do echo synthetic-diagnostic >&2; i=$((i+1)); done\nexit 24\n'
    )
    browser.chmod(0o700)
    result = probe(str(browser), {}, tmp_path / "profile")[0]
    assert result["exit_code"] == 24
    assert len(result["stderr"]) <= 20
