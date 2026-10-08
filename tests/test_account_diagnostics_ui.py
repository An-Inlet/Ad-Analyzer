"""Public read-only shell; native API/browser qualification follows frozen backend."""

from pathlib import Path

from app.main import app
from fastapi.testclient import TestClient


def test_account_diagnostics_shell_and_asset_are_separate_from_execution() -> None:
    with TestClient(app) as client:
        response = client.get("/app/account-diagnostics")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert "script-src 'self'" in response.headers["content-security-policy"]
        assert "unsafe-inline" not in response.headers["content-security-policy"]
        assert "does not require a spending mandate" in response.text
        assert "Optimization Is Unavailable" in response.text
        assert "Read Account Diagnostics" in response.text
        assert "Read Native Targets" in response.text
        assert client.get("/app/assets/native-targets.mjs").status_code == 200
        assert client.get("/app/assets/account-diagnostics.mjs").status_code == 200
        assert "/app/account-diagnostics" in client.get("/app/settings").text
    script = Path("app/portal/static/account-diagnostics.mjs").read_text()
    assert "innerHTML" not in script and "localStorage" not in script
