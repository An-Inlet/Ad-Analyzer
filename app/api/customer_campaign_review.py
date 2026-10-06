from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select

from app.campaign_review import service
from app.campaign_review.contracts import (
    MAX_IMAGE_BYTES,
    ExactApproval,
    MediaStore,
    RevisionEdit,
    RevisionInput,
)
from app.campaign_review.models import MediaObject
from app.campaign_review.storage import get_media_store
from app.customers.access import Database, MutationPrincipal, Principal, customer_workspace

router = APIRouter(prefix="/api/customer/v1", tags=["customer"])
Store = Annotated[MediaStore, Depends(get_media_store)]


def access(db: Database, user: str, wid: int, write: bool) -> None:
    _, role = customer_workspace(db, user, wid)
    if write and role not in {"owner", "admin"}:
        raise HTTPException(403, "insufficient role")


@router.post("/workspaces/{workspace_id}/media")
async def upload(
    workspace_id: int,
    request: Request,
    principal: MutationPrincipal,
    db: Database,
    store: Store,
    response: Response,
) -> dict[str, Any]:
    access(db, principal.user.id, workspace_id, True)
    response.headers["Cache-Control"] = "no-store"
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_IMAGE_BYTES:
            raise HTTPException(413, "image size exceeds limit")
        data.extend(chunk)
    row = service.upload(db, workspace_id, principal.user.id, bytes(data), store, datetime.now(UTC))
    return {
        "media_id": row.id,
        "sha256": row.sha256,
        "mime": row.mime,
        "width": row.width,
        "height": row.height,
        "size": row.size,
        "storage_mode": "private_local_development",
    }


@router.get("/workspaces/{workspace_id}/media/{media_id}")
def download(
    workspace_id: int, media_id: str, principal: Principal, db: Database, store: Store
) -> Response:
    access(db, principal.user.id, workspace_id, False)
    row, content = service.download(db, workspace_id, media_id, store)
    return Response(
        content,
        media_type=row.mime,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


@router.post("/workspaces/{workspace_id}/campaign-drafts")
def create(
    workspace_id: int,
    body: RevisionInput,
    principal: MutationPrincipal,
    db: Database,
    store: Store,
    response: Response,
) -> dict[str, Any]:
    access(db, principal.user.id, workspace_id, True)
    response.headers["Cache-Control"] = "no-store"
    return service.view(
        service.revise(db, workspace_id, body, principal.user.id, store, datetime.now(UTC))
    )


@router.put("/workspaces/{workspace_id}/campaign-drafts/{draft_id}")
def edit(
    workspace_id: int,
    draft_id: str,
    body: RevisionEdit,
    principal: MutationPrincipal,
    db: Database,
    store: Store,
    response: Response,
) -> dict[str, Any]:
    access(db, principal.user.id, workspace_id, True)
    response.headers["Cache-Control"] = "no-store"
    return service.view(
        service.revise(
            db,
            workspace_id,
            body.definition,
            principal.user.id,
            store,
            datetime.now(UTC),
            draft_id,
            body.expected_revision,
        )
    )


@router.get("/workspaces/{workspace_id}/campaign-drafts/{draft_id}/preview")
def preview(
    workspace_id: int,
    draft_id: str,
    principal: Principal,
    db: Database,
    store: Store,
    response: Response,
) -> dict[str, Any]:
    access(db, principal.user.id, workspace_id, False)
    response.headers["Cache-Control"] = "no-store"
    row, _ = service.preview(db, workspace_id, draft_id, store, datetime.now(UTC))
    return service.view(row)


@router.post("/workspaces/{workspace_id}/campaign-drafts/{draft_id}/approve")
def approve(
    workspace_id: int,
    draft_id: str,
    body: ExactApproval,
    principal: MutationPrincipal,
    db: Database,
    store: Store,
    response: Response,
) -> dict[str, Any]:
    access(db, principal.user.id, workspace_id, True)
    response.headers["Cache-Control"] = "no-store"
    return service.view(
        service.approve(
            db,
            workspace_id,
            draft_id,
            body.expected_revision,
            body.review_digest,
            principal.user.id,
            store,
            datetime.now(UTC),
        )
    )


@router.get("/workspaces/{workspace_id}/media")
def library(
    workspace_id: int, principal: Principal, db: Database, response: Response
) -> list[dict[str, Any]]:
    access(db, principal.user.id, workspace_id, False)
    response.headers["Cache-Control"] = "no-store"
    return [
        {
            "media_id": row.id,
            "sha256": row.sha256,
            "mime": row.mime,
            "width": row.width,
            "height": row.height,
            "size": row.size,
        }
        for row in db.scalars(
            select(MediaObject)
            .where(MediaObject.workspace_id == workspace_id)
            .order_by(MediaObject.created_at, MediaObject.id)
            .limit(100)
        )
    ]


@router.get("/workspaces/{workspace_id}/campaign-drafts")
def drafts(
    workspace_id: int, principal: Principal, db: Database, response: Response
) -> list[dict[str, Any]]:
    from app.campaign_review.models import CampaignDraft, CampaignRevision

    access(db, principal.user.id, workspace_id, False)
    response.headers["Cache-Control"] = "no-store"
    rows = db.scalars(
        select(CampaignRevision)
        .join(
            CampaignDraft,
            (CampaignDraft.id == CampaignRevision.draft_id)
            & (CampaignDraft.workspace_id == CampaignRevision.workspace_id)
            & (CampaignDraft.revision == CampaignRevision.revision),
        )
        .where(CampaignDraft.workspace_id == workspace_id)
        .order_by(CampaignRevision.created_at.desc(), CampaignRevision.draft_id)
        .limit(100)
    )
    return [
        {
            "draft_id": row.draft_id,
            "revision": row.revision,
            "name": row.artifact["definition"]["content"]["name"],
        }
        for row in rows
    ]
