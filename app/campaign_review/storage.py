"""Private local development storage; explicitly disabled by default, not cloud durability."""

import hashlib
import os
import re
import stat
from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException

from app.campaign_review.contracts import MAX_MEDIA_BYTES, MediaStore
from app.settings import settings


class LocalMediaStore:
    def __init__(self, root: Path) -> None:
        if not root.is_absolute() or root.is_symlink():
            raise ValueError("private absolute media directory required")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root = root

    def _directory(self, wid: int, sha: str) -> int:
        if wid <= 0 or not re.fullmatch(r"[a-f0-9]{64}", sha):
            raise ValueError("invalid media scope")
        root = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            with suppress(FileExistsError):
                os.mkdir(str(wid), mode=0o700, dir_fd=root)
            return os.open(str(wid), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root)
        finally:
            os.close(root)

    def put_if_absent(
        self, workspace_id: int, sha256: str, size: int, chunks: Iterable[bytes]
    ) -> None:
        if not 0 < size <= MAX_MEDIA_BYTES:
            raise ValueError("media size unavailable")
        directory = self._directory(workspace_id, sha256)
        temp = uuid4().hex
        try:
            fd = os.open(
                temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory
            )
            measured, checksum = 0, hashlib.sha256()
            with os.fdopen(fd, "wb") as file:
                for chunk in chunks:
                    measured += len(chunk)
                    if len(chunk) > 1024 * 1024 or measured > size:
                        raise ValueError("media exceeds declared bound")
                    checksum.update(chunk)
                    file.write(chunk)
                if measured != size or checksum.hexdigest() != sha256:
                    raise ValueError("media integrity mismatch")
                file.flush()
                os.fsync(file.fileno())
                os.fchmod(file.fileno(), 0o400)
            try:
                os.link(
                    temp, sha256, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False
                )
            except FileExistsError:
                self.read_exact(workspace_id, sha256, size)
        finally:
            with suppress(FileNotFoundError):
                os.unlink(temp, dir_fd=directory)
            os.close(directory)

    def read_exact(self, workspace_id: int, sha256: str, size: int) -> bytes:
        if not 0 < size <= MAX_MEDIA_BYTES:
            raise ValueError("media size unavailable")
        directory = self._directory(workspace_id, sha256)
        try:
            fd = os.open(sha256, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            with os.fdopen(fd, "rb") as file:
                if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
                    raise ValueError("regular private media object required")
                data = file.read(size + 1)
            if len(data) != size or hashlib.sha256(data).hexdigest() != sha256:
                raise ValueError("media integrity mismatch")
            return data
        finally:
            os.close(directory)


def get_media_store() -> MediaStore:
    if settings.media_storage_mode == "gcs" and settings.media_gcs_bucket:
        from google.cloud import storage  # type: ignore[attr-defined]

        from app.campaign_review.gcs_storage import GCSMediaStore

        try:
            if os.environ.get("STORAGE_EMULATOR_HOST"):
                raise ValueError("storage emulator is not a production media backend")
            return GCSMediaStore(
                settings.media_gcs_bucket,
                storage.Client(client_options={"api_endpoint": "https://storage.googleapis.com"}),
            )
        except Exception:
            raise HTTPException(503, "private media storage unavailable") from None
    if settings.media_storage_mode != "local_dev" or not settings.media_local_directory:
        raise HTTPException(503, "private media storage unavailable")
    try:
        return LocalMediaStore(Path(settings.media_local_directory))
    except (ValueError, OSError):
        raise HTTPException(503, "private media storage unavailable") from None
