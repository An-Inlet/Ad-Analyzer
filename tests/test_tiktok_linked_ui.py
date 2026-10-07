"""Real DOM/media tests with response fixtures; not configured API qualification."""

import functools
import hashlib
import http.server
import json
import shutil
import ssl
import subprocess
import threading
from pathlib import Path
from typing import Any

from app.main import app
from fastapi.testclient import TestClient

from tests.test_campaign_review import png
from tests.test_campaign_video import encoded as encoded
from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_portal import portal_executable


def test_linked_shell_and_javascript() -> None:
    with TestClient(app) as client:
        response = client.get("/app/tiktok-linked")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert "unsafe-inline" not in response.headers["content-security-policy"]
        assert "Commercial Music" in response.text
    subprocess.run(
        [portal_executable("node"), "--check", "app/portal/static/tiktok-linked.mjs"], check=True
    )


def test_linked_dom_exact_media_consent_and_stale_responses(tmp_path: Path, encoded: Any) -> None:
    browser = portal_executable("chromium", "chromium-browser", "google-chrome")
    (tmp_path / "index.html").write_text(
        Path("app/portal/static/tiktok-linked.html")
        .read_text()
        .replace("/app/assets/tiktok-linked.mjs", "/driver.mjs")
    )
    assets = tmp_path / "app/assets"
    assets.mkdir(parents=True)
    for name in ("tiktok-linked.mjs", "execution-media.mjs", "portal.css"):
        shutil.copyfile(Path("app/portal/static") / name, assets / name)
    media = {}
    for name, content, mime in (("video", encoded(), "video/mp4"), ("cover", png(), "image/png")):
        (tmp_path / name).write_bytes(content)
        media[name] = dict(
            media_id=name,
            mime=mime,
            size=len(content),
            byte_size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            width=64,
            height=64,
        )
    (tmp_path / "driver.mjs").write_text(
        Path("tests/javascript/tiktok_linked_dom.mjs")
        .read_text()
        .replace("__MEDIA__", json.dumps(media))
    )
    finished = threading.Event()
    outcome = []

    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_POST(self) -> None:
            assert self.path == "/__result__"
            outcome.append(self.rfile.read(int(self.headers["Content-Length"])).decode())
            self.send_response(200)
            self.end_headers()
            finished.set()

    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Handler, directory=str(tmp_path))
    )
    cert, key = localhost_certificate(tmp_path)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    process = subprocess.Popen(
        [
            browser,
            "--headless",
            "--no-sandbox",
            "--disable-gpu",
            "--ignore-certificate-errors",
            "--disable-background-networking",
            "--no-first-run",
            "--disable-extensions",
            "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
            f"--user-data-dir={tmp_path / 'browser'}",
            f"https://127.0.0.1:{server.server_port}/index.html",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert finished.wait(45), "Linked DOM browser did not finish"
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
