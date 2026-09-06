import csv
import json
from datetime import UTC, datetime
from io import StringIO
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dashboard.auth import require_dashboard_session, validate_csrf
from app.dashboard.intelligence import _csv_cell, _workspace
from app.dashboard.router import page_context, templates
from app.database.session import get_db
from app.settings import settings
from app.shopify.models import ShopifyAudit, ShopifyOrder, ShopifyPrivacyRequest
from app.shopify.reporting import sales_report
from app.shopify.security import ShopifyError, configuration_ready, verify_callback
from app.shopify.service import ConnectionService
from app.shopify.sync import ShopifySyncService, syncing_allowed
from app.workspaces.access import require_workspace_review
from app.workspaces.models import Workspace

router = APIRouter(prefix="/dashboard", dependencies=[Depends(require_dashboard_session)])
MESSAGES = {
    "connected": "Store connected. Start the first import below; larger stores "
    "finish over several sync cycles.",
    "disconnected": "Store disconnected and its imported sales removed. You can also "
    "uninstall Ad Analyzer in Shopify to revoke access there.",
    "complete": "Sales import completed.",
    "syncing": "This batch is saved. Continue the import below or let the "
    "scheduled worker finish it.",
    "disabled": "Sales imports are paused. Review the workspace automation controls.",
    "up_to_date": "Sales are already up to date.",
    "retry_later": "Shopify asked us to wait. Retry after the time shown below.",
    "not_connected_or_busy": "The store needs a connection or another import is already running.",
    "delivered": "The privacy request was marked delivered.",
}


def _actor(request: Request) -> str:
    return str(getattr(request.state, "dashboard_identity", "local-operator")).casefold()


async def _form(request: Request) -> dict[str, Any]:
    values = dict(await request.form(max_fields=10, max_files=0))
    request.scope["_form"] = values
    validate_csrf(request)
    return values


def _redirect(slug: str, message: str) -> RedirectResponse:
    # Only locally generated, fixed status codes reach the redirect.
    return RedirectResponse(
        f"/dashboard/workspaces/{slug}/shopify?notice={message}", status_code=303
    )


@router.get("/workspaces/{workspace_slug}/shopify", response_class=HTMLResponse)
def overview(
    request: Request, workspace_slug: str, db: Annotated[Session, Depends(get_db)]
) -> HTMLResponse:
    workspace, role = _workspace(request, db, workspace_slug)
    editable = role in {"platform_admin", "owner", "admin"}
    pending = (
        list(
            db.scalars(
                select(ShopifyPrivacyRequest)
                .where(
                    ShopifyPrivacyRequest.workspace_id == workspace.id,
                    ShopifyPrivacyRequest.completed_at.is_(None),
                )
                .order_by(ShopifyPrivacyRequest.requested_at)
                .limit(25)
            )
        )
        if editable
        else []
    )
    return templates.TemplateResponse(
        request,
        "shopify.html",
        page_context(
            request,
            title=f"{workspace.name} · Shopify sales",
            workspace=workspace,
            report=sales_report(db, workspace.id),
            can_edit=editable,
            configured=configuration_ready(settings),
            enabled=syncing_allowed(db, workspace.id),
            notice=MESSAGES.get(request.query_params.get("notice", "")),
            pending=pending,
        ),
    )


@router.post("/workspaces/{workspace_slug}/shopify/connect")
async def connect(
    request: Request, workspace_slug: str, db: Annotated[Session, Depends(get_db)]
) -> RedirectResponse:
    workspace, _role = _workspace(request, db, workspace_slug, edit=True)
    values = await _form(request)
    try:
        location = ConnectionService(db, settings).begin(
            workspace.id, str(values.get("shop", "")), _actor(request), datetime.now(UTC)
        )
    except ShopifyError:
        raise HTTPException(
            422,
            "Unable to start Shopify authorization. Check the store domain and integration setup.",
        ) from None
    return RedirectResponse(location, status_code=303)


@router.get("/shopify/callback")
def callback(request: Request, db: Annotated[Session, Depends(get_db)]) -> RedirectResponse:
    try:
        if not configuration_ready(settings) or not settings.shopify_client_secret:
            raise ShopifyError("shopify_configuration_required")
        now = datetime.now(UTC)
        values = verify_callback(
            request.query_params.multi_items(),
            settings.shopify_client_secret.get_secret_value(),
            now,
        )
        service = ConnectionService(db, settings)
        state = service.pending(values, _actor(request), now)
        role = require_workspace_review(request, db, state.workspace_id)
        workspace = db.get(Workspace, state.workspace_id)
        if workspace is None:
            raise ShopifyError("invalid_oauth_state")
        service.finish(state, values["code"], role, now)
        return _redirect(workspace.slug, "connected")
    except ShopifyError:
        db.rollback()
        raise HTTPException(
            422,
            "Shopify authorization could not be completed. Return to the workspace and reconnect.",
        ) from None


@router.post("/workspaces/{workspace_slug}/shopify/sync")
async def sync(
    request: Request, workspace_slug: str, db: Annotated[Session, Depends(get_db)]
) -> RedirectResponse:
    workspace, _role = _workspace(request, db, workspace_slug, edit=True)
    await _form(request)
    # One bounded page keeps this operator action within the web request deadline.
    result = ShopifySyncService(db, settings).page(workspace.id, manual=True)
    status = result["status"]
    if status not in MESSAGES:
        raise HTTPException(
            503, "Shopify sales could not be refreshed. Check connection status and retry later."
        )
    return _redirect(workspace.slug, status)


@router.post("/workspaces/{workspace_slug}/shopify/disconnect")
async def disconnect(
    request: Request, workspace_slug: str, db: Annotated[Session, Depends(get_db)]
) -> RedirectResponse:
    workspace, role = _workspace(request, db, workspace_slug, edit=True)
    values = await _form(request)
    if values.get("remove_imported_sales") != "confirmed":
        raise HTTPException(422, "Confirm removal of imported sales to disconnect.")
    ConnectionService(db, settings).disconnect(workspace.id, role)
    return _redirect(workspace.slug, "disconnected")


@router.get("/workspaces/{workspace_slug}/shopify/sales.csv")
def export(
    request: Request, workspace_slug: str, db: Annotated[Session, Depends(get_db)]
) -> Response:
    workspace, _role = _workspace(request, db, workspace_slug)
    report = sales_report(db, workspace.id)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["section", "metric", "value", "currency", "period_start", "period_end"])
    if report["connected"]:
        for key, value in report["current"].items():
            writer.writerow(
                [
                    "order cohort",
                    key,
                    _csv_cell(value),
                    report["currency_code"],
                    report["window"]["start"],
                    report["window"]["end"],
                ]
            )
        for note in [report["basis"], report["attribution_basis"], *report["warnings"]]:
            writer.writerow(["basis", "note", _csv_cell(note)])
        writer.writerow(["status", "complete_and_fresh", report["ready"]])
        for product in report["products"]:
            writer.writerow(
                ["product", _csv_cell(product["title"]), product["ordered_units"], "ordered units"]
            )
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="shopify-sales.csv"'},
    )


@router.get("/workspaces/{workspace_slug}/shopify/privacy/{request_id}.json")
def privacy_export(
    request: Request, workspace_slug: str, request_id: int, db: Annotated[Session, Depends(get_db)]
) -> Response:
    workspace, _role = _workspace(request, db, workspace_slug, edit=True)
    item = db.scalar(
        select(ShopifyPrivacyRequest).where(
            ShopifyPrivacyRequest.id == request_id,
            ShopifyPrivacyRequest.workspace_id == workspace.id,
        )
    )
    if item is None:
        raise HTTPException(404, "request not found")
    orders: list[ShopifyOrder] = []
    for offset in range(0, len(item.order_keys), 500):
        orders.extend(
            db.scalars(
                select(ShopifyOrder).where(
                    ShopifyOrder.workspace_id == workspace.id,
                    ShopifyOrder.connection_id == item.connection_id,
                    ShopifyOrder.order_key.in_(item.order_keys[offset : offset + 500]),
                )
            )
        )
    payload = {
        "requested_at": item.requested_at.isoformat(),
        "records": [
            {
                "created_at": o.created_at.isoformat(),
                "currency": o.currency_code,
                "net_collected_micros": o.net_collected_micros,
                "refunded_micros": o.refunded_micros,
                "cancelled": o.cancelled,
                "customer_order_index": o.customer_order_index,
                "channel": o.channel,
                "products": o.products,
                "source_updated_at": o.source_updated_at.isoformat(),
                "products_complete": o.products_complete,
                "campaign_id": o.campaign_id,
            }
            for o in orders
        ],
        "note": "All retained order facts for this request. Names, email, "
        "addresses and customer IDs are not collected. Internal "
        "deduplication hashes are excluded.",
    }
    return Response(
        json.dumps(payload),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="shopify-privacy-request.json"'},
    )


@router.post("/workspaces/{workspace_slug}/shopify/privacy/{request_id}/delivered")
async def privacy_delivered(
    request: Request, workspace_slug: str, request_id: int, db: Annotated[Session, Depends(get_db)]
) -> RedirectResponse:
    workspace, role = _workspace(request, db, workspace_slug, edit=True)
    await _form(request)
    item = db.scalar(
        select(ShopifyPrivacyRequest)
        .where(
            ShopifyPrivacyRequest.id == request_id,
            ShopifyPrivacyRequest.workspace_id == workspace.id,
        )
        .with_for_update()
    )
    if item is None:
        raise HTTPException(404, "request not found")
    if item.completed_at is None:
        item.completed_at = datetime.now(UTC)
        db.add(ShopifyAudit(workspace_id=workspace.id, action="privacy_delivered", actor_role=role))
        db.commit()
    return _redirect(workspace.slug, "delivered")
