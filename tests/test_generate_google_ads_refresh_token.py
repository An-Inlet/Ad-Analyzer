import sys
from importlib import import_module
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

google_auth_oauthlib_module = ModuleType("google_auth_oauthlib")
flow_module = ModuleType("google_auth_oauthlib.flow")
flow_module.__dict__["InstalledAppFlow"] = object
sys.modules.setdefault("google_auth_oauthlib", google_auth_oauthlib_module)
sys.modules.setdefault("google_auth_oauthlib.flow", flow_module)
refresh_token_script = import_module("scripts.generate_google_ads_refresh_token")


class FakeFlow:
    def __init__(self) -> None:
        self.local_server_args: dict[str, Any] | None = None

    def run_local_server(self, **kwargs: Any) -> SimpleNamespace:
        self.local_server_args = kwargs
        return SimpleNamespace(refresh_token="test-refresh-token")


def test_refresh_token_script_uses_secure_file_helper(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "google-ads-refresh-token.env"
    desktop_oauth_json = tmp_path / "desktop-oauth.json"
    fake_flow = FakeFlow()
    helper_calls: list[tuple[Path, str]] = []

    class FakeInstalledAppFlow:
        @staticmethod
        def from_client_secrets_file(file_path: str, scopes: list[str]) -> FakeFlow:
            assert file_path == str(desktop_oauth_json)
            assert scopes == [refresh_token_script.GOOGLE_ADS_SCOPE]
            return fake_flow

    def fake_secure_write_refresh_token_file(path: Path, contents: str) -> None:
        helper_calls.append((path, contents))

    def fail_write_text(self: Path, *args: Any, **kwargs: Any) -> str:
        raise AssertionError("script must use secure_write_refresh_token_file")

    def fail_chmod(self: Path, mode: int, *, follow_symlinks: bool = True) -> None:
        raise AssertionError("script must not chmod after writing token data")

    monkeypatch.setattr(
        refresh_token_script,
        "parse_args",
        lambda: SimpleNamespace(
            desktop_oauth_json=desktop_oauth_json,
            output=output_path,
            port=4321,
        ),
    )
    monkeypatch.setattr(refresh_token_script, "InstalledAppFlow", FakeInstalledAppFlow)
    monkeypatch.setattr(
        refresh_token_script,
        "secure_write_refresh_token_file",
        fake_secure_write_refresh_token_file,
    )
    monkeypatch.setattr(Path, "write_text", fail_write_text)
    monkeypatch.setattr(Path, "chmod", fail_chmod)

    refresh_token_script.main()

    assert helper_calls == [
        (output_path, "GOOGLE_ADS_REFRESH_TOKEN=test-refresh-token\n"),
    ]
    assert fake_flow.local_server_args == {
        "port": 4321,
        "access_type": "offline",
        "prompt": "consent",
    }
    assert not output_path.exists()
