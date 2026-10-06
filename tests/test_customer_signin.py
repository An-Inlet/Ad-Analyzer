"""Browser identity wiring stays offline, origin-bound and revocable."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from app.customers.access import CSRF_COOKIE
from app.main import app
from app.portal.auth import browser_identity_config, customer_content_security_policy
from app.settings import settings
from fastapi.testclient import TestClient

from tests.test_customer_identity import (  # noqa: F401
    ORIGIN,
    FakeProvider,
    customer_engine,
    replicas,
)
from tests.test_customer_portal import portal_executable


def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "customer_auth_enabled", True)
    monkeypatch.setattr(settings, "customer_browser_auth_enabled", True)
    monkeypatch.setattr(settings, "customer_identity_project_id", "inlet-test")
    monkeypatch.setattr(settings, "customer_identity_web_api_key", "fixture_public_" + "x" * 24)
    monkeypatch.setattr(settings, "customer_identity_web_app_id", "1:123:web:abcdef")
    monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)
    monkeypatch.delenv("FIREBASE_AUTH_EMULATOR_HOST", raising=False)


def test_browser_config_disabled_by_default_and_no_external_csp() -> None:
    with TestClient(app) as client:
        response = client.get("/api/customer/v1/auth-config")
    assert response.json() == {
        "enabled": False,
        "providers": [],
        "live_verified": False,
        "firebase": None,
    }
    assert response.headers["cache-control"] == "no-store"
    assert "https://" not in customer_content_security_policy()


def test_enabled_public_config_and_fixed_csp(monkeypatch: pytest.MonkeyPatch) -> None:
    enabled(monkeypatch)
    config = browser_identity_config()
    assert config.enabled and config.providers == ["google.com"] and not config.live_verified
    assert config.firebase and config.firebase["authDomain"] == "inlet-test.firebaseapp.com"
    policy = customer_content_security_policy()
    assert "script-src 'self' https://apis.google.com;" in policy
    assert "frame-src https://inlet-test.firebaseapp.com;" in policy
    assert "unsafe-" not in policy and "*" not in policy
    monkeypatch.setattr(settings, "customer_identity_project_id", "bad.test/; script-src *")
    assert not browser_identity_config().enabled
    assert "https://" not in customer_content_security_policy()


@pytest.mark.parametrize(
    "field,value",
    [
        ("customer_auth_enabled", False),
        ("customer_browser_auth_enabled", False),
        ("customer_identity_web_api_key", ""),
        ("customer_identity_web_app_id", ""),
        ("customer_app_origin", "http://inlet.example"),
    ],
)
def test_partial_configuration_fails_closed(
    monkeypatch: pytest.MonkeyPatch, field: str, value: object
) -> None:
    enabled(monkeypatch)
    monkeypatch.setattr(settings, field, value)
    assert not browser_identity_config().enabled


def test_signup_exchange_workspace_repeat_and_revocation(
    replicas: tuple[TestClient, TestClient, FakeProvider],  # noqa: F811
) -> None:
    client, stranger, _ = replicas
    assert client.get("/api/customer/v1/session").status_code == 401
    response = client.post(
        "/api/customer/v1/session",
        json={"id_token": "new-google-subject:first"},
        headers={"Origin": ORIGIN, "X-Inlet-Request": "1"},
    )
    assert response.status_code == 200
    assert all(
        "Secure" in c and "SameSite=strict" in c for c in response.headers.get_list("set-cookie")
    )
    assert "HttpOnly" in response.headers.get_list("set-cookie")[0]
    headers = {
        "Origin": ORIGIN,
        "X-CSRF-Token": client.cookies[CSRF_COOKIE],
        "Idempotency-Key": "signup-attempt-1234",
    }
    workspace = client.post(
        "/api/customer/v1/workspaces",
        json={"slug": "new-shop", "name": "New Shop"},
        headers=headers,
    )
    assert workspace.status_code == 201, workspace.text
    assert (
        client.post(
            "/api/customer/v1/workspaces",
            json={"slug": "new-shop", "name": "New Shop"},
            headers=headers,
        ).json()
        == workspace.json()
    )
    assert (
        client.post(
            "/api/customer/v1/session",
            json={"id_token": "new-google-subject:first"},
            headers={"Origin": ORIGIN, "X-Inlet-Request": "1"},
        ).status_code
        == 401
    )
    assert stranger.get(f"/api/customer/v1/workspaces/{workspace.json()['id']}").status_code == 401
    assert client.delete("/api/customer/v1/session", headers=headers).status_code == 204
    assert client.get("/api/customer/v1/workspaces").status_code == 401


def test_signin_js_contracts_and_pinned_bundle() -> None:
    subprocess.run(
        [portal_executable("node"), "--test", "tests/javascript/customer_signin.test.mjs"],
        check=True,
    )
    lock = json.loads(Path("browser/auth/package-lock.json").read_text())
    assert lock["packages"]["node_modules/firebase"]["version"] == "12.19.0"
    assert lock["packages"]["node_modules/esbuild"]["version"] == "0.28.2"
    assert Path("app/portal/static/firebase-auth.mjs").stat().st_size > 100000


def test_signin_in_local_browser(tmp_path: Path) -> None:
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
            'src="/app/assets/portal.mjs"', 'src="/tests/javascript/customer_signin_browser.mjs"'
        )
    )
    (tmp_path / "index.html").write_text(html)
    assets = tmp_path / "app/assets"
    assets.mkdir(parents=True)
    for name in ("portal.mjs", "portal.css", "auth.mjs"):
        shutil.copyfile(Path("app/portal/static") / name, assets / name)
    (assets / "firebase-auth.mjs").write_text("""
export const inMemoryPersistence={}, browserPopupRedirectResolver={};
export const initializeApp=()=>({}), initializeAuth=()=>({});
export class GoogleAuthProvider {setCustomParameters() {}}
export const signInWithPopup=async()=>({user:{getIdToken:async()=> 'fixture-token'}});
export const signOut=async()=>{globalThis.sdkClears=(globalThis.sdkClears||0)+1;};
export const deleteApp=async()=>{};
""")
    shutil.copyfile("app/portal/static/firebase-auth.mjs", assets / "firebase-bundle.mjs")
    scripts = tmp_path / "tests/javascript"
    scripts.mkdir(parents=True)
    shutil.copyfile(
        "tests/javascript/customer_signin_browser.mjs", scripts / "customer_signin_browser.mjs"
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
