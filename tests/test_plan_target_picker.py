"""Real Chromium component checks; server receipts and authenticated wiring tested separately."""

import functools
import json
import os
import shutil
import signal
import subprocess
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from app.planning_catalog.projection_v2 import project_v2

from tests.test_customer_portal import portal_executable
from tests.test_planning_metadata_binding import bundle


@pytest.mark.parametrize("driver", ["plan_target_picker_dom", "plan_scenarios_dom"])
def test_target_picker_exact_choices_revocation_expiry_and_bounds(
    tmp_path: Path, driver: str
) -> None:
    chromium = portal_executable("chromium", "chromium-browser", "google-chrome")
    catalogs = [
        project_v2(*bundle(platform)).model_dump(mode="json")
        for platform in ("google", "meta", "tiktok")
    ]
    (tmp_path / "catalogs.json").write_text(json.dumps(catalogs))
    for name in ("plan-target-picker.mjs", "native-targets.mjs", "plan-scenarios.mjs"):
        shutil.copy(Path("app/portal/static") / name, tmp_path / name)
    (tmp_path / "index.html").write_text(
        '<div id="host"></div><pre id="result"></pre><script type="module" src="test.mjs"></script>'
    )
    shutil.copy(f"tests/javascript/{driver}.mjs", tmp_path / "test.mjs")
    complete = threading.Event()
    reports: list[str] = []

    class Handler(SimpleHTTPRequestHandler):
        def do_POST(self) -> None:
            length = min(int(self.headers.get("Content-Length", "0")), 10000)
            reports.append(self.rfile.read(length).decode())
            self.send_response(200)
            self.end_headers()
            complete.set()

    handler = functools.partial(Handler, directory=str(tmp_path))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    browser = subprocess.Popen(
        [
            chromium,
            "--headless",
            "--no-sandbox",
            "--disable-gpu",
            f"--user-data-dir={tmp_path / 'browser'}",
            f"http://127.0.0.1:{server.server_port}/index.html",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        assert complete.wait(15), "Browser did not report a document result"
        assert reports == ["PASS"], reports
    finally:
        os.killpg(browser.pid, signal.SIGTERM)
        try:
            browser.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(browser.pid, signal.SIGKILL)
            browser.wait(timeout=5)
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
