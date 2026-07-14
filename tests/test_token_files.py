import os
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from app.token_files import PRIVATE_TOKEN_FILE_MODE, write_refresh_token_file


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

    write_refresh_token_file(output_file, "test-refresh-token")

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
    if os.name != "nt":
        assert mode_before_write == [PRIVATE_TOKEN_FILE_MODE]


def test_refresh_token_file_refuses_to_overwrite_existing_file(tmp_path: Path) -> None:
    output_file = tmp_path / "google-refresh-token.txt"
    output_file.write_bytes(b"existing-token-data")

    with pytest.raises(FileExistsError):
        write_refresh_token_file(output_file, "replacement-token")

    assert output_file.read_bytes() == b"existing-token-data"


def test_refresh_token_file_refuses_to_follow_symlink(tmp_path: Path) -> None:
    target_file = tmp_path / "target-token.txt"
    target_file.write_bytes(b"existing-token-data")
    output_file = tmp_path / "google-refresh-token.txt"
    try:
        output_file.symlink_to(target_file)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"Symlink creation is unavailable in this environment: {exc}")

    with pytest.raises(FileExistsError):
        write_refresh_token_file(output_file, "replacement-token")

    assert output_file.is_symlink()
    assert target_file.read_bytes() == b"existing-token-data"
