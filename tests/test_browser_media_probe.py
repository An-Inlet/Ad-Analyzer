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


def test_startup_evidence_is_bounded_and_does_not_echo_targets(tmp_path: Path) -> None:
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from scripts.check_browser_media import startup_evidence

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            pass

        def do_GET(self) -> None:
            data = ({"Browser": "synthetic"} if self.path == "/json/version" else [
                {"type": "page", "url": "http://127.0.0.1:1234/"},
                {"type": "page", "url": "sensitive-synthetic-url"},
            ])
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    (tmp_path / "DevToolsActivePort").write_text(str(server.server_port) + "\nunused\n")
    try:
        result = startup_evidence(tmp_path, "http://127.0.0.1:1234/")
        assert result == {"devtools_ready": True, "version": "ready",
                          "page_targets": 2, "expected_navigation": True}
        assert "sensitive" not in json.dumps(result)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize("port_file", ["", "not-a-port", "65536", "-1"])
def test_startup_evidence_rejects_invalid_port(tmp_path: Path, port_file: str) -> None:
    from scripts.check_browser_media import startup_evidence

    (tmp_path / "DevToolsActivePort").write_text(port_file)
    assert startup_evidence(tmp_path, "http://127.0.0.1/") == {"devtools_ready": False}


def test_probe_cleans_up_browser_child_after_parent_exit(tmp_path: Path) -> None:
    import os
    import sys
    import time

    if os.name != "posix":
        pytest.skip("POSIX browser process-group cleanup")
    pid_file = tmp_path / "child-pid"
    browser = tmp_path / "browser"
    browser.write_text(
        f"#!{sys.executable}\nimport os, signal, time\n"
        "child = os.fork()\n"
        "if child == 0:\n"
        " signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        " time.sleep(60)\n"
        "else:\n"
        f" open({str(pid_file)!r}, 'w').write(str(child))\n"
        " time.sleep(0.1)\n"
        " os._exit(23)\n"
    )
    browser.chmod(0o700)
    result = probe(str(browser), {}, tmp_path / "profile")[0]
    assert result["exit_code"] == 23
    assert result["loopback_ready"] is True
    assert result["first_request_seconds"] is None
    assert result["startup"] == {"devtools_ready": False}
    pid = int(pid_file.read_text())
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        status = Path(f"/proc/{pid}/stat")
        if not status.exists() or status.read_text().split()[2] == "Z":
            break
        time.sleep(0.01)
    else:
        pytest.fail("browser child survived isolated group cleanup")
