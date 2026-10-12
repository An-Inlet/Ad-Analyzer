"""Lazy existing private storage for owned planner reads; no blob upload capability."""

from collections.abc import Iterable

from app.campaign_review.storage import get_media_store


class ConfiguredPlanningMedia:
    def read_exact(self, workspace_id: int, sha256: str, size: int) -> bytes:
        # OwnedPlanningImageReader performs authority/metadata checks before this call.
        # Keep initialization lazy so disabled storage cannot block immutable history.
        return get_media_store().read_exact(workspace_id, sha256, size)

    def put_if_absent(
        self, workspace_id: int, sha256: str, size: int, chunks: Iterable[bytes]
    ) -> None:
        raise ValueError("planning media is read-only")
