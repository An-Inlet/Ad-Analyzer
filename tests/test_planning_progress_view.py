"""Real Chromium DOM test of display-only documents; not an authenticated API journey."""

import functools
import os
import shutil
import signal
import subprocess
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from tests.test_customer_portal import portal_executable


def test_progress_exact_amount_scope_and_unavailable_dom(tmp_path: Path) -> None:
    chromium = portal_executable("chromium", "chromium-browser", "google-chrome")
    shutil.copy("app/portal/static/plan-progress.mjs", tmp_path / "plan-progress.mjs")
    shutil.copy("tests/javascript/plan_progress_dom.mjs", tmp_path / "test.mjs")
    (tmp_path / "index.html").write_text(
        '<!doctype html><main id="host"></main><script type="module" src="/test.mjs"></script>'
    )
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
