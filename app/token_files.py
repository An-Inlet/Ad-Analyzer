import errno
import os
import stat
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


def write_refresh_token_file(path: Path, refresh_token: str) -> None:
    """Create a new private refresh-token file and write token data to it."""
    fd = _open_private_new_file(path)
    try:
        _set_private_file_permissions(fd)
        _write_all(fd, refresh_token.encode("utf-8"))
        os.fsync(fd)
    except BaseException:
        with suppress(OSError):
            os.close(fd)
        with suppress(OSError):
            path.unlink(missing_ok=True)
        raise
    os.close(fd)
