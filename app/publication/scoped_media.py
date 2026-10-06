"""DB-owned private media bridge for concrete social transports; no runtime factory."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.campaign_review.contracts import MediaStore
from app.campaign_review.models import MediaObject
from app.campaign_review.service import inspect_media
from app.campaign_review.video import validate_video
from app.publication.contracts import fingerprint
from app.publication.social_contracts import ProviderMediaBinding


class ScopedProviderMediaReader:
    def __init__(self, db: Session, store: MediaStore) -> None:
        self.db, self.store = db, store

    def binding(self, workspace_id: int, media_id: str) -> ProviderMediaBinding:
        row = self.db.scalar(
            select(MediaObject)
            .where(MediaObject.workspace_id == workspace_id, MediaObject.id == media_id)
            .execution_options(populate_existing=True)
        )
        if row is None:
            raise ValueError("owned media unavailable")
        raw = self.store.read_exact(workspace_id, row.sha256, row.size)
        if row.mime == "video/mp4":
            video = validate_video(raw)
            mime, width, height, duration = (
                "video/mp4",
                video.width,
                video.height,
                video.duration_ms,
            )
        else:
            mime, width, height = inspect_media(raw)
            duration = None
        if (mime, width, height) != (row.mime, row.width, row.height):
            raise ValueError("media validation changed")
        details = dict(
            media_id=row.id,
            sha256=row.sha256,
            byte_size=row.size,
            mime=mime,
            width=width,
            height=height,
            duration_ms=duration,
            validation_version="video_v1" if duration is not None else "image_v1",
        )
        return ProviderMediaBinding.model_validate(
            {
                **details,
                "validation_digest": fingerprint("inlet.private-media-validation.v1", details),
            }
        )

    def read_verified(self, workspace_id: int, binding: ProviderMediaBinding) -> bytes:
        current = self.binding(workspace_id, binding.media_id)
        if current != binding:
            raise ValueError("reviewed media changed")
        return self.store.read_exact(workspace_id, binding.sha256, binding.byte_size)
