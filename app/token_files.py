import errno
import getpass
import os
import stat
import subprocess
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Final, cast

PRIVATE_TOKEN_FILE_MODE: Final = stat.S_IRUSR | stat.S_IWUSR


def _open_private_new_file(path: Path) -> int:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)

    try:
        return os.open(path, flags, PRIVATE_TOKEN_FILE_MODE)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise FileExistsError("Refresh-token output file already exists") from exc
        raise


def _write_all(fd: int, data: bytes) -> None:
    remaining = data
    while remaining:
        bytes_written = os.write(fd, remaining)
        if bytes_written == 0:
            raise OSError("Failed to write refresh-token file")
        remaining = remaining[bytes_written:]


def _set_private_file_permissions(fd: int) -> None:
    fchmod = cast(Callable[[int, int], None] | None, getattr(os, "fchmod", None))
    if fchmod is not None:
        fchmod(fd, PRIVATE_TOKEN_FILE_MODE)


def _current_windows_user() -> str:
    username = os.environ.get("USERNAME") or getpass.getuser()
    domain = os.environ.get("USERDOMAIN")
    if domain and "\\" not in username and "@" not in username:
        return f"{domain}\\{username}"
    return username


def _run_windows_acl_command(path: Path, *arguments: str) -> None:
    try:
        completed = subprocess.run(
            ["icacls", os.fspath(path), *arguments],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise PermissionError("Failed to secure refresh-token file ACL") from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        message = "Failed to secure refresh-token file ACL"
        if detail:
            message = f"{message}: {detail}"
        raise PermissionError(message)


def _set_private_windows_acl(path: Path) -> None:
    user = _current_windows_user()
    _run_windows_acl_command(path, "/grant:r", f"{user}:F")
    _run_windows_acl_command(path, "/inheritance:r")


def _secure_new_file_before_write(fd: int, path: Path) -> None:
    if os.name == "nt":
        _set_private_windows_acl(path)
        return
    _set_private_file_permissions(fd)


def secure_write_refresh_token_file(path: Path, contents: str) -> None:
    """Create a new private refresh-token file and write token data to it."""
    fd = _open_private_new_file(path)
    try:
        _secure_new_file_before_write(fd, path)
        _write_all(fd, contents.encode("utf-8"))
        os.fsync(fd)
    except BaseException:
        with suppress(OSError):
            os.close(fd)
        with suppress(OSError):
            path.unlink(missing_ok=True)
        raise
    os.close(fd)


def write_refresh_token_file(path: Path, refresh_token: str) -> None:
    secure_write_refresh_token_file(path, refresh_token)
