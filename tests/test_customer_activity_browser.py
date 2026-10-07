import shutil
import subprocess
from pathlib import Path

from tests.test_customer_portal import portal_executable


def test_customer_activity_in_local_browser(tmp_path: Path) -> None:
    """Exercise actual DOM events in Chromium; fixture fetch never reaches providers."""
    import functools
    import http.server
    import threading

    chromium = portal_executable(
        "chromium", "chromium-browser", "google-chrome", "google-chrome-stable"
    )
    html = (
        Path("app/portal/static/activity.html")
        .read_text()
        .replace(
            'src="/app/assets/activity.mjs"',
            'src="/tests/javascript/customer_activity_browser.mjs"',
        )
    )
    (tmp_path / "index.html").write_text(html)
    assets = tmp_path / "app/assets"
    assets.mkdir(parents=True)
    for name in ("activity.mjs", "portal.css"):
        shutil.copyfile(Path("app/portal/static") / name, assets / name)
    scripts = tmp_path / "tests/javascript"
    scripts.mkdir(parents=True)
    shutil.copyfile(
        "tests/javascript/customer_activity_browser.mjs", scripts / "customer_activity_browser.mjs"
    )
    finished = threading.Event()
    outcome: list[str] = []

    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_POST(self) -> None:
            assert self.path == "/__result__"
            outcome.append(self.rfile.read(int(self.headers["Content-Length"])).decode())
            self.send_response(200)
            self.end_headers()
            finished.set()

    handler = functools.partial(Handler, directory=str(tmp_path))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    process = subprocess.Popen(
        [
            chromium,
            "--headless",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-background-networking",
            "--no-first-run",
            "--disable-extensions",
            "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
            f"--user-data-dir={tmp_path / 'browser'}",
            f"http://127.0.0.1:{server.server_port}/index.html",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert finished.wait(60), "Browser fixture did not report completion"
        assert outcome == ["passed"], outcome
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
