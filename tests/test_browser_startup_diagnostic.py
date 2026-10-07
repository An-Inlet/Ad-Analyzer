import json
import shutil
import subprocess
from pathlib import Path

import pytest
from scripts import diagnose_browser_startup as diagnostic


@pytest.mark.parametrize("event", ["error", "loadeddata", "browser_no_result"])
def test_startup_collection_never_qualifies_or_exports_browser(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str], event: str
) -> None:
    monkeypatch.setattr("sys.argv", ["diagnostic"])
    export = tmp_path / "github-env"
    monkeypatch.setenv("GITHUB_ENV", str(export))
    monkeypatch.setattr(shutil, "which", lambda name: "/offline/browser")
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw:
                        subprocess.CompletedProcess(a, 0, "synthetic version", ""))
    calls: list[str] = []

    def probe(browser: str, clips: dict[str, bytes], directory: Path) -> list[dict[str, str]]:
        calls.append(browser)
        assert clips == {"/silent": b"", "/aac": b""}
        return [{"event": event}]

    monkeypatch.setattr(diagnostic, "probe", probe)
    assert diagnostic.main() == 0
    assert calls == ["/offline/browser"]  # Both aliases/families resolve to same binary.
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert all(record["codec_qualification"] == "not_attempted" for record in records)
    assert records[-1]["browser_count"] == 1
    assert not export.exists()


def test_diagnostic_has_no_install_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["diagnostic"])
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: pytest.fail("no install"))
    assert diagnostic.main() == 2


def test_diagnostic_rejects_export_option(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["diagnostic", "--github-env", "/tmp/not-written"])
    with pytest.raises(SystemExit) as caught:
        diagnostic.main()
    assert caught.value.code == 2


def test_each_family_attempted_once_after_launch_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["diagnostic"])
    monkeypatch.setattr(shutil, "which", lambda name: "/offline/" + name)
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw:
                        subprocess.CompletedProcess(a, 0, "synthetic", ""))
    calls: list[str] = []

    def probe(browser: str, clips: dict[str, bytes], directory: Path) -> list[dict[str, str]]:
        calls.append(browser)
        raise OSError("must not echo arbitrary error contents")

    monkeypatch.setattr(diagnostic, "probe", probe)
    assert diagnostic.main() == 0
    assert calls == ["/offline/google-chrome", "/offline/chromium"]
    output = capsys.readouterr().out
    assert "must not echo" not in output
    assert output.count("browser_launch_unavailable") == 2
