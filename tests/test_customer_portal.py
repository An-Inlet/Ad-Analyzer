"""The shell is public; data and mutations remain on customer-authenticated APIs."""

import os
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
    assert "Inlet cannot publish, activate, pause or change advertising." in response.text
    assert "this is not a production purchase offer." in response.text
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


def portal_executable(*names: str) -> str:
    browsers = {"chromium", "chromium-browser", "google-chrome", "google-chrome-stable"}
    selected = os.environ.get("INLET_TEST_BROWSER")
    if selected and browsers.intersection(names):
        executable = shutil.which(selected)
        if not executable:
            pytest.fail("Configured codec-qualified browser is unavailable")
        return executable
    # Branded Chrome includes H.264/AAC; unbranded snapshot builds may omit them.
    if browsers.intersection(names):
        names = tuple(
            n
            for n in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
            if n in names
        )
    for name in names:
        executable = shutil.which(name)
        if executable:
            return executable
    message = f"Customer portal checks require one of: {', '.join(names)}"
    if os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI") == "true":
        pytest.fail(message + "; hosted CI must not skip this check")
    pytest.skip(message + "; install locally to run this check")


def test_portal_javascript_contracts() -> None:
    node = portal_executable("node")
    subprocess.run([node, "--test", "tests/javascript/customer_portal.test.mjs"], check=True)


def test_customer_journey_in_local_browser(tmp_path: Path) -> None:
    """Exercise actual DOM events in Chromium; fixture fetch never reaches providers."""
    import functools
    import http.server
    import threading

    chromium = portal_executable(
        "chromium", "chromium-browser", "google-chrome", "google-chrome-stable"
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


@pytest.mark.parametrize("name", ["node", "google-chrome"])
def test_missing_portal_dependency_fails_in_ci(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.delenv("INLET_TEST_BROWSER", raising=False)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    with pytest.raises(pytest.fail.Exception, match="hosted CI must not skip"):
        portal_executable(name)


def test_google_chrome_is_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INLET_TEST_BROWSER", raising=False)
    monkeypatch.setattr(
        shutil, "which", lambda name: "/usr/bin/google-chrome" if name == "google-chrome" else None
    )
    assert portal_executable("chromium", "chromium-browser", "google-chrome") == (
        "/usr/bin/google-chrome"
    )


def test_codec_qualified_browser_selection_is_shared(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INLET_TEST_BROWSER", "/fixture/qualified-chrome")
    monkeypatch.setattr(
        shutil, "which", lambda name: name if name == "/fixture/qualified-chrome" else None
    )
    assert portal_executable("chromium", "google-chrome") == "/fixture/qualified-chrome"
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(pytest.fail.Exception, match="codec-qualified browser is unavailable"):
        portal_executable("chromium", "google-chrome")


def test_local_browser_prefers_codec_capable_brand_without_changing_node(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("INLET_TEST_BROWSER", raising=False)
    monkeypatch.setattr(shutil, "which", lambda name: "/fixture/" + name)
    assert portal_executable("chromium", "google-chrome") == "/fixture/google-chrome"
    assert portal_executable("node") == "/fixture/node"
