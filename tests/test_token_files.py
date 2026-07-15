import os
import stat
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from app import token_files
from app.token_files import PRIVATE_TOKEN_FILE_MODE, secure_write_refresh_token_file


def test_refresh_token_file_is_created_private_before_writing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_file = tmp_path / "google-refresh-token.txt"
    open_flags: list[int] = []
    open_modes: list[int] = []
    fchmod_modes: list[int] = []
    mode_before_write: list[int] = []
    original_open = os.open
    original_write = os.write
    original_fchmod = cast(Callable[[int, int], None] | None, getattr(os, "fchmod", None))
    actual_os_name = os.name
    monkeypatch.setattr(os, "name", "posix")

    def recording_open(
        path: Any,
        flags: int,
        mode: int = 0o777,
        *args: Any,
        **kwargs: Any,
    ) -> int:
        assert args == ()
        assert kwargs == {}
        open_flags.append(flags)
        open_modes.append(mode)
        return original_open(path, flags, mode)

    def recording_write(fd: int, data: bytes) -> int:
        if not mode_before_write:
            assert fchmod_modes == [PRIVATE_TOKEN_FILE_MODE]
            mode_before_write.append(stat.S_IMODE(output_file.stat().st_mode))
        return original_write(fd, data)

    def recording_fchmod(fd: int, mode: int) -> None:
        fchmod_modes.append(mode)
        if original_fchmod is not None:
            original_fchmod(fd, mode)

    monkeypatch.setattr(os, "open", recording_open)
    monkeypatch.setattr(os, "write", recording_write)
    monkeypatch.setattr(os, "fchmod", recording_fchmod, raising=False)

    secure_write_refresh_token_file(output_file, "test-refresh-token")

    assert output_file.read_text(encoding="utf-8") == "test-refresh-token"
    assert open_modes == [PRIVATE_TOKEN_FILE_MODE]
    assert fchmod_modes == [PRIVATE_TOKEN_FILE_MODE]
    assert len(open_flags) == 1
    assert (open_flags[0] & os.O_CREAT) == os.O_CREAT
    assert (open_flags[0] & os.O_EXCL) == os.O_EXCL
    assert (open_flags[0] & os.O_TRUNC) == 0
    nofollow_flag = getattr(os, "O_NOFOLLOW", 0)
    if nofollow_flag:
        assert (open_flags[0] & nofollow_flag) == nofollow_flag
    if actual_os_name != "nt":
        assert mode_before_write == [PRIVATE_TOKEN_FILE_MODE]


def test_windows_private_directory_is_verified_before_writing_token_data(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_file = tmp_path / "google-refresh-token.txt"
    events: list[str] = []
    acl_queries: list[list[str]] = []
    original_open = os.open
    original_write_all = token_files._write_all

    def recording_run(
        command: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        assert check is False
        assert capture_output is True
        assert text is True
        events.append("acl")
        acl_queries.append(command)
        acl_output = (
            f"{output_file.parent} TESTDOMAIN\\TestUser:(OI)(CI)(F)\n"
            "Successfully processed 1 files; Failed processing 0 files\n"
        )
        return subprocess.CompletedProcess(command, 0, stdout=acl_output, stderr="")

    def recording_open(
        path: Any,
        flags: int,
        mode: int = 0o777,
        *args: Any,
        **kwargs: Any,
    ) -> int:
        assert args == ()
        assert kwargs == {}
        assert events == ["acl"]
        events.append("open")
        return original_open(path, flags, mode)

    def recording_write_all(fd: int, data: bytes) -> None:
        assert events == ["acl", "open"]
        events.append("write")
        original_write_all(fd, data)

    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setenv("USERDOMAIN", "TESTDOMAIN")
    monkeypatch.setenv("USERNAME", "TestUser")
    monkeypatch.setattr(subprocess, "run", recording_run)
    monkeypatch.setattr(os, "open", recording_open)
    monkeypatch.setattr(token_files, "_write_all", recording_write_all)

    secure_write_refresh_token_file(output_file, "test-refresh-token")

    assert events == ["acl", "open", "write"]
    assert acl_queries == [["icacls", str(output_file.parent)]]
    assert output_file.read_text(encoding="utf-8") == "test-refresh-token"


def test_windows_non_private_directory_refuses_before_file_creation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_file = tmp_path / "google-refresh-token.txt"
    acl_queries: list[list[str]] = []

    def shared_directory_run(
        command: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        assert check is False
        assert capture_output is True
        assert text is True
        acl_queries.append(command)
        acl_output = (
            f"{output_file.parent} TESTDOMAIN\\TestUser:(OI)(CI)(F)\n"
            r"BUILTIN\Users:(I)(RX)"
            "\nSuccessfully processed 1 files; Failed processing 0 files\n"
        )
        return subprocess.CompletedProcess(command, 0, stdout=acl_output, stderr="")

    def fail_open(
        path: Any,
        flags: int,
        mode: int = 0o777,
        *args: Any,
        **kwargs: Any,
    ) -> int:
        raise AssertionError("token file must not be created in a non-private directory")

    def fail_write_all(fd: int, data: bytes) -> None:
        raise AssertionError("token data must not be written in a non-private directory")

    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setenv("USERDOMAIN", "TESTDOMAIN")
    monkeypatch.setenv("USERNAME", "TestUser")
    monkeypatch.setattr(subprocess, "run", shared_directory_run)
    monkeypatch.setattr(os, "open", fail_open)
    monkeypatch.setattr(token_files, "_write_all", fail_write_all)

    with pytest.raises(PermissionError, match="not private"):
        secure_write_refresh_token_file(output_file, "test-refresh-token")

    assert acl_queries == [["icacls", str(output_file.parent)]]
    assert not output_file.exists()


def test_refresh_token_file_refuses_to_overwrite_existing_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(os, "name", "posix")
    output_file = tmp_path / "google-refresh-token.txt"
    output_file.write_bytes(b"existing-token-data")

    with pytest.raises(FileExistsError):
        secure_write_refresh_token_file(output_file, "replacement-token")

    assert output_file.read_bytes() == b"existing-token-data"


def test_refresh_token_file_refuses_to_follow_symlink(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(os, "name", "posix")
    target_file = tmp_path / "target-token.txt"
    target_file.write_bytes(b"existing-token-data")
    output_file = tmp_path / "google-refresh-token.txt"
    try:
        output_file.symlink_to(target_file)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"Symlink creation is unavailable in this environment: {exc}")

    with pytest.raises(FileExistsError):
        secure_write_refresh_token_file(output_file, "replacement-token")

    assert output_file.is_symlink()
    assert target_file.read_bytes() == b"existing-token-data"
