"""The shell is public; data and mutations remain on customer-authenticated APIs."""

import shutil
import subprocess
from pathlib import Path

import pytest
from app.main import app
from fastapi.testclient import TestClient


@pytest.mark.parametrize("path", ["/app", "/app/", "/app/settings"])
def test_customer_shell_has_strict_headers_and_no_inline_code(path: str) -> None:
    with TestClient(app) as client:
        response = client.get(path)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    policy = response.headers["content-security-policy"]
    assert "script-src 'self'" in policy
    assert "connect-src 'self'" in policy
    assert "frame-ancestors 'none'" in policy
    assert "unsafe-inline" not in policy
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "Sign In Required" in response.text
    assert "Live advertising execution is disabled" in response.text
    assert "id_token" not in response.text
    assert '<script type="module" src=' in response.text
    assert "onclick=" not in response.text


def test_assets_and_existing_routes_are_separate() -> None:
    with TestClient(app) as client:
        assert client.get("/app/assets/portal.mjs").status_code == 200
        assert client.get("/app/assets/portal.css").status_code == 200
        assert client.get("/app/assets/../router.py").status_code == 404
        assert client.get("/app/unknown").status_code == 404
        assert client.get("/").json()["name"] == "ad-analyzer"
    script = Path("app/portal/static/portal.mjs").read_text()
    assert "innerHTML" not in script
    assert "localStorage" not in script
    assert "textContent" in script


def test_portal_javascript_contracts() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for browser-independent JavaScript contract tests")
    subprocess.run([node, "--test", "tests/javascript/customer_portal.test.mjs"], check=True)


def test_customer_journey_in_local_browser(tmp_path: Path) -> None:
    """Exercise actual DOM events in Chromium; fixture fetch never reaches providers."""
    import functools
    import http.server
    import threading

    chromium = shutil.which("chromium") or shutil.which("chromium-browser")
    if chromium is None:
        pytest.skip(
            "Chromium unavailable; browser journey must run in a browser-enabled environment"
        )
    html = (
        Path("app/portal/static/index.html")
        .read_text()
        .replace(
            'src="/app/assets/portal.mjs"', 'src="/tests/javascript/customer_portal_browser.mjs"'
        )
    )
    (tmp_path / "index.html").write_text(html)
    assets = tmp_path / "app/assets"
    assets.mkdir(parents=True)
    for name in ("portal.mjs", "portal.css"):
        shutil.copyfile(Path("app/portal/static") / name, assets / name)
    scripts = tmp_path / "tests/javascript"
    scripts.mkdir(parents=True)
    shutil.copyfile(
        "tests/javascript/customer_portal_browser.mjs", scripts / "customer_portal_browser.mjs"
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
        assert finished.wait(20), "Browser fixture did not report completion"
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
