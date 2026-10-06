import hashlib
import io
import warnings
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform
from app.billing.entitlements import paid_work
from app.campaign_review.contracts import (
    MAX_IMAGE_BYTES,
    MAX_LIBRARY_BYTES,
    MAX_MEDIA_BYTES,
    MAX_PIXELS,
    MediaRef,
    MediaStore,
    ReviewArtifact,
    RevisionInput,
)
from app.campaign_review.models import CampaignDraft, CampaignRevision, MediaObject
from app.campaign_review.video import VideoInvalid, VideoUnavailable, validate_video
from app.google_connections.models import GoogleCustomerConnection
from app.imports.scope import AdvertisingImportScope, ImportScopeError, validate_advertising_scope
from app.mandates import service as mandates
from app.meta.models import MetaConnection
from app.sources.models import SourceConnection
from app.workspaces.models import Workspace


def inspect_media(data: bytes) -> tuple[str, int, int]:
    if not 0 < len(data) <= MAX_MEDIA_BYTES:
        raise HTTPException(413, "media size exceeds limit")
    if data[4:8] == b"ftyp":
        try:
            info = validate_video(data)
        except VideoUnavailable:
            raise HTTPException(503, "video validation unavailable") from None
        except VideoInvalid:
            raise HTTPException(422, "valid bounded H264 MP4 with optional AAC required") from None
        return "video/mp4", info.width, info.height
    if not 0 < len(data) <= MAX_IMAGE_BYTES:
        raise HTTPException(413, "image size exceeds limit")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data), formats=["JPEG", "PNG"]) as image:
                width, height = image.size
                if (
                    width * height > MAX_PIXELS
                    or width < 1
                    or height < 1
                    or getattr(image, "n_frames", 1) != 1
                ):
                    raise ValueError("image dimensions unavailable")
                mime = "image/png" if image.format == "PNG" else "image/jpeg"
                image.verify()
            with Image.open(io.BytesIO(data), formats=["JPEG", "PNG"]) as decoded:
                decoded.load()
    except Exception:
        raise HTTPException(422, "valid bounded static JPEG or PNG required") from None
    return mime, width, height


def upload(
    db: Session, wid: int, actor: str, data: bytes, store: MediaStore, now: datetime
) -> MediaObject:
    workspace = db.scalar(
        select(Workspace)
        .where(Workspace.id == wid)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if workspace is None or workspace.status != "active":
        raise HTTPException(404, "workspace unavailable")
    paid_work(db, wid, now)
    mime, width, height = inspect_media(data)
    sha = hashlib.sha256(data).hexdigest()
    existing = db.scalar(
        select(MediaObject).where(MediaObject.workspace_id == wid, MediaObject.sha256 == sha)
    )
    if existing:
        return existing
    count, used = db.execute(
        select(func.count(), func.coalesce(func.sum(MediaObject.size), 0)).where(
            MediaObject.workspace_id == wid
        )
    ).one()
    if count >= 100 or used + len(data) > MAX_LIBRARY_BYTES:
        raise HTTPException(409, "development media library quota reached")
    try:
        store.put_if_absent(
            wid,
            sha,
            len(data),
            (data[i : i + 1024 * 1024] for i in range(0, len(data), 1024 * 1024)),
        )
    except (OSError, ValueError):
        raise HTTPException(503, "private media storage unavailable") from None
    row = MediaObject(
        id=uuid4().hex,
        workspace_id=wid,
        sha256=sha,
        size=len(data),
        mime=mime,
        width=width,
        height=height,
        created_by=actor,
        created_at=now,
    )
    db.add(row)
    db.commit()
    return row


def media(db: Session, wid: int, media_id: str) -> MediaObject:
    row = db.scalar(
        select(MediaObject).where(MediaObject.workspace_id == wid, MediaObject.id == media_id)
    )
    if row is None:
        raise HTTPException(404, "media unavailable")
    return row


def download(db: Session, wid: int, media_id: str, store: MediaStore) -> tuple[MediaObject, bytes]:
    row = media(db, wid, media_id)
    try:
        return row, store.read_exact(wid, row.sha256, row.size)
    except (OSError, ValueError):
        raise HTTPException(503, "private media integrity unavailable") from None


def binding(db: Session, wid: int, definition: RevisionInput, now: datetime) -> str:
    paid_work(db, wid, now)
    mandate = mandates.owned(db, wid, definition.mandate_id)
    policy = mandates.policy(db, mandate)
    mandates.validate(db, mandate, policy, now)
    if (
        mandate.revision != definition.mandate_revision
        or mandate.state != "approved"
        or mandate.paused
        or now >= policy.ends_at
        or definition.account not in policy.accounts
        or "new_campaign" not in policy.allowed_actions
        or policy.currency != definition.currency
        or not policy.starts_at <= definition.starts_at < definition.ends_at <= policy.ends_at
        or definition.budget_micros > min(policy.total_cap_micros, policy.per_action_cap_micros)
    ):
        raise HTTPException(409, "approved mandate does not cover campaign draft")
    try:
        validate_advertising_scope(
            db,
            AdvertisingImportScope(
                wid,
                definition.account.connection_id,
                definition.account.account_id,
                AdvertisingPlatform(definition.account.platform),
            ),
        )
    except ImportScopeError:
        raise HTTPException(409, "advertising ownership unavailable") from None
    if definition.account.platform == "google_ads":
        row = db.scalar(
            select(GoogleCustomerConnection)
            .where(
                GoogleCustomerConnection.workspace_id == wid,
                GoogleCustomerConnection.integration_id == definition.account.connection_id,
                GoogleCustomerConnection.account_id == definition.account.account_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    elif definition.account.platform == "meta_ads":
        meta = db.scalar(
            select(MetaConnection)
            .where(
                MetaConnection.workspace_id == wid,
                MetaConnection.workspace_integration_id == definition.account.connection_id,
                MetaConnection.account_id == definition.account.account_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if meta is None or meta.status != "connected":
            raise HTTPException(409, "current connection unavailable")
        return f"meta:{meta.id}:{meta.generation}"
    else:
        source = db.scalar(
            select(SourceConnection)
            .where(
                SourceConnection.workspace_id == wid,
                SourceConnection.integration_id == definition.account.connection_id,
                SourceConnection.account_id == definition.account.account_id,
                SourceConnection.provider == "tiktok_ads",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if source is None or source.status != "connected":
            raise HTTPException(409, "current connection unavailable")
        return f"tiktok:{source.id}:{source.generation}"
    if row is None or row.status != "connected":
        raise HTTPException(409, "current connection unavailable")
    return f"google:{row.id}:{row.generation}"


def artifact(
    db: Session, draft: CampaignDraft, definition: RevisionInput, store: MediaStore, now: datetime
) -> ReviewArtifact:
    version = binding(db, draft.workspace_id, definition, now)
    refs: list[MediaRef] = []
    blockers: list[str] = []
    content = definition.content
    if content.kind != "google_search_v1":
        row, data = download(db, draft.workspace_id, content.media.media_id, store)
        if row.sha256 != content.media.sha256:
            raise HTTPException(409, "media reference changed")
        refs = [content.media]
        expected = (
            {"video/mp4"}
            if content.kind == "tiktok_website_conversion_video_v1"
            else {"image/jpeg", "image/png"}
        )
        if row.mime not in expected:
            raise HTTPException(422, "campaign media type mismatch")
        verified_mime, width, height = inspect_media(data)
        if (verified_mime, width, height) != (row.mime, row.width, row.height):
            raise HTTPException(409, "media validation changed")
    return ReviewArtifact(
        draft_id=draft.id,
        revision=draft.revision,
        workspace_id=draft.workspace_id,
        definition=definition,
        connection_version=version,
        media=refs,
        offline_reviewable=not blockers,
        blockers=blockers,
    )


def owned(db: Session, wid: int, draft_id: str) -> CampaignDraft:
    mandates.workspace_lock(db, wid)
    row = db.scalar(
        select(CampaignDraft)
        .where(CampaignDraft.id == draft_id, CampaignDraft.workspace_id == wid)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise HTTPException(404, "campaign draft unavailable")
    return row


def revise(
    db: Session,
    wid: int,
    definition: RevisionInput,
    actor: str,
    store: MediaStore,
    now: datetime,
    draft_id: str | None = None,
    expected: int | None = None,
) -> CampaignRevision:
    definition = RevisionInput.model_validate(definition.model_dump(mode="json"))
    mandates.workspace_lock(db, wid)
    if draft_id:
        draft = owned(db, wid, draft_id)
        if draft.revision != expected:
            raise HTTPException(409, "campaign draft changed")
        draft.revision += 1
    else:
        draft = CampaignDraft(id=uuid4().hex, workspace_id=wid, revision=1)
        db.add(draft)
    document = artifact(db, draft, definition, store, now)
    db.flush()
    row = CampaignRevision(
        draft_id=draft.id,
        revision=draft.revision,
        workspace_id=wid,
        artifact=document.model_dump(mode="json"),
        digest=document.fingerprint(),
        created_by=actor,
        created_at=now,
    )
    db.add(row)
    db.commit()
    return row


def preview(
    db: Session, wid: int, draft_id: str, store: MediaStore, now: datetime
) -> tuple[CampaignRevision, ReviewArtifact]:
    draft = owned(db, wid, draft_id)
    row = db.get(CampaignRevision, (draft.id, draft.revision))
    assert row is not None
    frozen = ReviewArtifact.model_validate(row.artifact)
    current = artifact(db, draft, frozen.definition, store, now)
    if current.fingerprint() != row.digest:
        raise HTTPException(409, "review bindings changed; create a new revision")
    return row, frozen


def approve(
    db: Session,
    wid: int,
    draft_id: str,
    expected: int,
    review_digest: str,
    actor: str,
    store: MediaStore,
    now: datetime,
) -> CampaignRevision:
    row, document = preview(db, wid, draft_id, store, now)
    if row.revision != expected or row.digest != review_digest or not document.offline_reviewable:
        raise HTTPException(409, "exact offline review unavailable or changed")
    if row.approved_by is None:
        row.approved_by, row.approved_at = actor, now
    db.commit()
    return row


def view(row: CampaignRevision) -> dict[str, Any]:
    return {
        "draft_id": row.draft_id,
        "revision": row.revision,
        "review_digest": row.digest,
        "artifact": row.artifact,
        "approved_for_offline_plan": row.approved_by is not None,
        "publication_eligible": False,
        "live_verified": False,
    }
