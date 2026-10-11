"""Actual planning controller with controlled Fetch; not authenticated API qualification."""

import functools
import os
import shutil
import signal
import subprocess
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from tests.test_customer_portal import portal_executable


def test_owner_review_controller_preserves_legacy_input_mode(tmp_path: Path) -> None:
    browser_path = portal_executable("chromium", "chromium-browser", "google-chrome")
    assets = tmp_path / "app" / "assets"
    assets.mkdir(parents=True)
    for source in Path("app/portal/static").glob("*.mjs"):
        shutil.copy(source, assets / source.name)
    page = Path("app/portal/static/planning.html").read_text()
    page = page.replace(
        '<script type="module" src="/app/assets/planning.mjs"></script>',
        '<script type="module" src="/test.mjs"></script>',
    )
    (tmp_path / "index.html").write_text(page)
    shutil.copy("tests/javascript/plan_google_owner_controller_dom.mjs", tmp_path / "test.mjs")
    complete = threading.Event()
    reports: list[str] = []

    class Handler(SimpleHTTPRequestHandler):
        def do_POST(self) -> None:
            length = min(int(self.headers.get("Content-Length", "0")), 10000)
            reports.append(self.rfile.read(length).decode())
            self.send_response(200)
            self.end_headers()
            complete.set()

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Handler, directory=str(tmp_path))
    )
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    browser = subprocess.Popen(
        [
            browser_path,
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
        assert complete.wait(15), "Controller did not report a result"
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
