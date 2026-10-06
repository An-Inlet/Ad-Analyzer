"""Owner/requester-bound ephemeral downloads. Archive construction runs in a worker thread."""

from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import Engine
from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse
from starlette.types import Receive, Scope, Send

from app.campaign_review.storage import get_media_store
from app.customers.access import Database, MutationPrincipal, Principal, Provider
from app.goals.schemas import StrictModel
from app.lifecycle import archive
from app.lifecycle.contracts import LifecycleInputV1, LifecycleScopeV1
from app.lifecycle.exports import SLOTS, Authority, Download
from app.lifecycle.models import LifecycleRequest, LifecycleStep
from app.lifecycle.quiescing import owner
from app.lifecycle.service import begin

router = APIRouter(prefix="/api/customer/v1", tags=["customer"])


class ExportResponse(StreamingResponse):
    def __init__(self, resource: Download, request_id: str) -> None:
        self.resource = resource
        super().__init__(
            resource.chunks(),
            media_type="application/x-tar",
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Content-Disposition": f'attachment; filename="inlet-export-{request_id}.tar"',
            },
            background=BackgroundTask(resource.close),
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            # ASGI send errors and disconnect cancellation can bypass BackgroundTask.
            self.resource.close()


class ExportInput(StrictModel):
    pass


def view(row: LifecycleRequest, step: LifecycleStep | None) -> dict[str, Any]:
    return {
        "schema_version": "inlet.export-request.v1",
        "request_id": row.id,
        "workspace_id": row.workspace_id,
        "state": row.state,
        "revision": row.revision,
        "snapshot": row.blockers,
        "manifest_sha256": step.evidence_digest if step else None,
        "delivery": "unconfirmed",
        "retained_artifact": False,
    }


@router.post("/workspaces/{workspace_id}/exports")
def create(
    workspace_id: int,
    body: ExportInput,
    request: Request,
    response: Response,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
) -> dict[str, Any]:
    keys = request.headers.getlist("idempotency-key")
    if len(keys) != 1:
        raise HTTPException(422, "invalid idempotency key")
    row = begin(
        db,
        principal,
        provider,
        LifecycleInputV1(scope=LifecycleScopeV1(workspace_id=workspace_id), operation="export"),
        keys[0],
        datetime.now(UTC),
    )
    result = view(row, db.get(LifecycleStep, (row.id, "export_build")))
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/workspaces/{workspace_id}/exports/{request_id}")
def status(
    workspace_id: int,
    request_id: str,
    response: Response,
    principal: Principal,
    provider: Provider,
    db: Database,
) -> dict[str, Any]:
    owner(db, principal, provider, workspace_id)
    row = db.get(LifecycleRequest, request_id)
    if (
        row is None
        or row.workspace_id != workspace_id
        or row.operation != "export"
        or row.requested_by != principal.user.id
    ):
        raise HTTPException(404, "export unavailable")
    response.headers["Cache-Control"] = "no-store"
    return view(row, db.get(LifecycleStep, (row.id, "export_build")))


@router.get("/workspaces/{workspace_id}/exports/{request_id}/download")
def download(
    workspace_id: int, request_id: str, principal: Principal, provider: Provider, db: Database
) -> StreamingResponse:
    engine = db.get_bind()
    if not isinstance(engine, Engine):
        raise HTTPException(503, "export database unavailable")
    authority = Authority(engine, principal, provider, workspace_id, request_id)
    db.rollback()  # Release request dependency transaction before independent snapshot/control IO.
    authority.check()
    if not SLOTS.acquire(blocking=False):
        raise HTTPException(429, "export capacity busy")
    file = None
    claimed = False
    try:
        revision, _ = authority.claim()
        claimed = True
        file, manifest = archive.build(
            engine, workspace_id, request_id, revision, get_media_store, authority.check
        )
        authority.check()
        authority.finish(manifest)
        resource = Download(file, authority)
        return ExportResponse(resource, request_id)
    except Exception as error:
        if file is not None:
            file.close()
        SLOTS.release()
        if claimed:
            # Original failure wins; expired running receipt never claims completion.
            with suppress(Exception):
                authority.finish(None)
        if isinstance(error, HTTPException):
            raise
        raise HTTPException(
            409, "export could not be built; no complete archive produced"
        ) from None
