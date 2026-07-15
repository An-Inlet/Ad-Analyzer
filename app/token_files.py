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
_ACL_ERROR = "Refresh-token output directory is not private to the current Windows user"
_FILE_ACL_ERROR = "Refresh-token output file ACL could not be restricted to the current user"
_WINDOWS_ALLOWED_ADMIN_IDENTITIES = frozenset(
    {
        "system",
        "nt authority\\system",
        "administrators",
        "builtin\\administrators",
    }
)


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


def _run_windows_acl_query(path: Path, error_message: str = _ACL_ERROR) -> str:
    try:
        completed = subprocess.run(
            ["icacls", os.fspath(path)],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise PermissionError(error_message) from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        message = error_message
        if detail:
            message = f"{message}: {detail}"
        raise PermissionError(message)
    return completed.stdout


def _run_windows_acl_update(path: Path, *arguments: str) -> None:
    try:
        completed = subprocess.run(
            ["icacls", os.fspath(path), *arguments],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise PermissionError(_FILE_ACL_ERROR) from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        message = _FILE_ACL_ERROR
        if detail:
            message = f"{message}: {detail}"
        raise PermissionError(message)


def _normalize_windows_identity(identity: str) -> str:
    return identity.strip().casefold()


def _iter_windows_acl_entries(path: Path, acl_output: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    path_text = os.fspath(path).casefold()
    for raw_line in acl_output.splitlines():
        line = raw_line.strip()
        if (
            not line
            or line.lower().startswith("successfully processed")
            or line.lower().startswith("failed processing")
        ):
            continue
        if raw_line.casefold().startswith(path_text):
            line = raw_line[len(os.fspath(path)) :].strip()
        marker_index = line.find(":(")
        if marker_index == -1:
            continue
        identity = line[:marker_index].strip()
        permissions = line[marker_index + 1 :].strip()
        entries.append((identity, permissions))
    return entries


def _verify_private_windows_directory(path: Path) -> None:
    if not path.is_dir():
        raise PermissionError(_ACL_ERROR)

    current_user = _normalize_windows_identity(_current_windows_user())
    entries = _iter_windows_acl_entries(path, _run_windows_acl_query(path))
    if not entries:
        raise PermissionError(_ACL_ERROR)

    for identity, permissions in entries:
        normalized_identity = _normalize_windows_identity(identity)
        normalized_permissions = permissions.upper()
        if "(DENY)" in normalized_permissions:
            raise PermissionError(_ACL_ERROR)
        if (
            normalized_identity != current_user
            and normalized_identity not in _WINDOWS_ALLOWED_ADMIN_IDENTITIES
        ):
            raise PermissionError(_ACL_ERROR)


def _verify_current_user_only_windows_file(path: Path) -> None:
    current_user = _normalize_windows_identity(_current_windows_user())
    entries = _iter_windows_acl_entries(path, _run_windows_acl_query(path, _FILE_ACL_ERROR))
    if len(entries) != 1:
        raise PermissionError(_FILE_ACL_ERROR)

    identity, permissions = entries[0]
    normalized_identity = _normalize_windows_identity(identity)
    normalized_permissions = permissions.upper()
    if normalized_identity != current_user:
        raise PermissionError(_FILE_ACL_ERROR)
    if "(I)" in normalized_permissions or "(DENY)" in normalized_permissions:
        raise PermissionError(_FILE_ACL_ERROR)
    if "(F)" not in normalized_permissions:
        raise PermissionError(_FILE_ACL_ERROR)


def _set_current_user_only_windows_file_acl(path: Path) -> None:
    user = _current_windows_user()
    _run_windows_acl_update(path, "/grant:r", f"{user}:F")
    _run_windows_acl_update(path, "/inheritance:r")
    _verify_current_user_only_windows_file(path)


def _secure_new_file_before_write(fd: int, path: Path) -> None:
    if os.name == "nt":
        _set_current_user_only_windows_file_acl(path)
        return
    _set_private_file_permissions(fd)


def secure_write_refresh_token_file(path: Path, contents: str) -> None:
    """Create a new private refresh-token file and write token data to it."""
    if os.name == "nt":
        _verify_private_windows_directory(path.parent)

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
