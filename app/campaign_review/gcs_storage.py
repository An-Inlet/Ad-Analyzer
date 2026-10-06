"""Immutable private GCS objects. No bucket provisioning, ACL mutations or public URLs."""

import hashlib
import io
import re
from collections.abc import Iterable
from contextlib import suppress

from google.api_core.exceptions import PreconditionFailed
from google.cloud import storage  # type: ignore[attr-defined]

from app.campaign_review.contracts import MAX_MEDIA_BYTES


class _BoundedBuffer(io.BytesIO):
    def __init__(self, limit: int) -> None:
        super().__init__()
        self.limit = limit

    def write(self, data: bytes, /) -> int:  # type: ignore[override]
        if self.tell() + len(data) > self.limit:
            raise ValueError("media exceeds declared bound")
        return super().write(data)


class GCSMediaStore:
    def __init__(self, bucket_name: str, client: storage.Client) -> None:
        # Deliberately exclude URLs, dotted hostnames and custom endpoints.
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,61}[a-z0-9]", bucket_name):
            raise ValueError("invalid private media bucket")
        self.bucket_name = bucket_name
        self.client = client

    def _key(self, workspace_id: int, sha256: str, size: int) -> str:
        if (
            type(workspace_id) is not int
            or workspace_id <= 0
            or not re.fullmatch(r"[a-f0-9]{64}", sha256)
            or type(size) is not int
            or not 0 < size <= MAX_MEDIA_BYTES
        ):
            raise ValueError("invalid media scope or size")
        return f"inlet/media/v1/workspaces/{workspace_id}/{sha256}"

    def _private_bucket(self) -> storage.Bucket:
        bucket = self.client.get_bucket(self.bucket_name, timeout=15, retry=None)
        policy = bucket.iam_configuration
        if (
            policy.uniform_bucket_level_access_enabled is not True
            or policy.public_access_prevention != "enforced"
        ):
            raise ValueError("private media bucket policy required")
        return bucket

    def put_if_absent(
        self, workspace_id: int, sha256: str, size: int, chunks: Iterable[bytes]
    ) -> None:
        key = self._key(workspace_id, sha256, size)
        with _BoundedBuffer(size) as source:
            checksum = hashlib.sha256()
            for chunk in chunks:
                if not isinstance(chunk, bytes) or len(chunk) > 1024 * 1024:
                    raise ValueError("invalid media chunk")
                source.write(chunk)
                checksum.update(chunk)
            if source.tell() != size or checksum.hexdigest() != sha256:
                raise ValueError("media integrity mismatch")
            source.seek(0)
            try:
                bucket = self._private_bucket()
                blob = bucket.blob(key)
                with suppress(PreconditionFailed):
                    blob.upload_from_file(
                        source,
                        size=size,
                        content_type="application/octet-stream",
                        if_generation_match=0,
                        # Own SHA verification avoids SDK corruption cleanup deletes.
                        checksum=None,
                        timeout=30,
                        retry=None,
                    )
                # A concurrent winner is accepted only after exact content verification.
                self.read_exact(workspace_id, sha256, size)
            except Exception:
                raise OSError("private media write unavailable") from None

    def read_exact(self, workspace_id: int, sha256: str, size: int) -> bytes:
        key = self._key(workspace_id, sha256, size)
        try:
            bucket = self._private_bucket()
            blob = bucket.blob(key)
            blob.reload(timeout=15, retry=None)
            generation = blob.generation
            if type(generation) is not int or generation <= 0 or blob.size != size:
                raise ValueError("media metadata mismatch")
            # Reconstruct the resource: never follow a metadata-provided mediaLink URL.
            blob = bucket.blob(key, generation=generation)
            with _BoundedBuffer(size) as target:
                blob.download_to_file(
                    target,
                    start=0,
                    end=size,
                    raw_download=True,
                    if_generation_match=generation,
                    timeout=30,
                    retry=None,
                    checksum="crc32c",
                )
                data = target.getvalue()
            if len(data) != size or hashlib.sha256(data).hexdigest() != sha256:
                raise ValueError("media integrity mismatch")
            self._private_bucket()
            return data
        except Exception:
            raise OSError("private media read unavailable") from None
