import csv
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from io import StringIO
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.intelligence import save_context, workspace_or_404
from app.dashboard.auth import require_dashboard_session, validate_csrf
from app.dashboard.router import page_context, templates
from app.database.session import get_db
from app.intelligence.repository import ContextConflict, ContextNotFound, IntelligenceRepository
from app.intelligence.schemas import (
    PAYLOAD_MODELS,
    AnalystQuestion,
    RecordKind,
    SaveRecord,
    ScenarioRequest,
)
from app.intelligence.service import IntelligenceService
from app.workspaces.access import (
    accessible_workspace_ids,
    require_workspace_review,
    require_workspace_view,
)
from app.workspaces.models import Workspace
from app.workspaces.repository import WorkspaceRepository

router = APIRouter(prefix="/dashboard", dependencies=[Depends(require_dashboard_session)])

LABELS = {
    "budget_micros": "Approved advertising budget",
    "primary_metric": "Primary business outcome",
    "target": "Target for this period",
    "contribution_margin_bps": "Contribution margin (%)",
    "maximum_cac_micros": "Maximum customer acquisition cost",
    "remaining_reserve_micros": "Remaining event budget to reserve",
    "amount_micros": "Operating cost amount",
    "minimum_lift_bps": "Minimum meaningful lift (percentage points)",
    "control_units": "Unique units assigned to control",
    "treatment_units": "Unique units assigned to treatment",
    "randomized_assignment": "Was assignment randomized?",
    "minimum_outcomes": "Minimum outcomes for comparisons",
    "evidence_reference": "Evidence reference (report name or internal reference)",
}
DESCRIPTIONS = {
    "strategy": (
        "Define the business result, budget, and priorities that should guide recommendations."
    ),
    "event": (
        "Plan preparation, campaign dates, and follow-up. Reserving "
        "money here does not change advertising spend."
    ),
    "creative": (
        "Describe a creative concept and its campaign. Comparisons use "
        "campaign context; they cannot isolate individual ads."
    ),
    "experiment": (
        "Predefine one comparison. Once the test starts, its design is "
        "locked; outcome counts remain editable."
    ),
    "cost": (
        "Record an invoice or estimate. These costs are separate from "
        "advertising spend and do not change any service."
    ),
    "change": (
        "Record a business change, the expected result, and when to "
        "evaluate it. Later observations do not by themselves prove "
        "causation."
    ),
    "decision": (
        "Record your review and follow-up. This does not execute "
        "advertising changes or authorize a financial transaction."
    ),
}
HIDDEN_FIELDS = {
    "evidence_scope",
    "evidence_snapshot",
    "recommendation_key",
    "evidence_fingerprint",
}


def _fields(kind: RecordKind, data: dict[str, Any]) -> list[dict[str, Any]]:
    schema = PAYLOAD_MODELS[kind].model_json_schema()
    fields = []
    today = datetime.now(UTC).date()
    for key, specification in schema["properties"].items():
        if key in HIDDEN_FIELDS:
            continue
        alternatives = specification.get("anyOf", [specification])
        shape = next(
            (s for s in alternatives if s.get("type") not in {"null", "string"}), alternatives[0]
        )
        if specification.get("format") == "date":
            shape = specification
        value = data.get(key, specification.get("default", ""))
        if key in {"starts_on", "period_start", "effective_on"} and not value:
            value = today.isoformat()
        if key in {"ends_on", "period_end", "review_on"} and not value:
            value = (today + timedelta(days=29)).isoformat()
        input_type = "text"
        if shape.get("type") in {"integer", "number"}:
            input_type = "number"
        if shape.get("format") == "date":
            input_type = "date"
        if value is None:
            value = ""
        if key.endswith("_micros") and value != "":
            value = Decimal(str(value)) / 1_000_000
        if key.endswith("_bps") and value != "":
            value = Decimal(str(value)) / 100
        options = specification.get("enum", [])
        if shape.get("type") == "boolean":
            options = ["false", "true"]
            value = "true" if value is True else "false"
        fields.append(
            {
                "name": key,
                "label": LABELS.get(key, key.replace("_", " ").capitalize()),
                "value": value,
                "type": input_type,
                "options": options,
                "required": key in schema.get("required", []),
                "textarea": specification.get("maxLength", 0) > 240 and key != "landing_page_path",
                "max_length": specification.get("maxLength", 2000),
                "step": "any"
                if key.endswith(("_micros", "_bps")) or shape.get("type") == "number"
                else "1",
            }
        )
    return fields


def _form_payload(kind: RecordKind, form: dict[str, Any]) -> dict[str, Any]:
    schema = PAYLOAD_MODELS[kind].model_json_schema()
    payload: dict[str, Any] = {}
    for key, spec in schema["properties"].items():
        if key in HIDDEN_FIELDS:
            if key in {"recommendation_key", "evidence_fingerprint"} and key in form:
                payload[key] = str(form[key])
            continue
        value = str(form.get(key, "")).strip()
        if value == "":
            if spec.get("default", "") is None:
                payload[key] = None
            elif key in schema.get("required", []):
                payload[key] = ""
            continue
        if key.endswith(("_micros", "_bps")):
            scale = 1_000_000 if key.endswith("_micros") else 100
            amount = Decimal(value) * scale
            if not amount.is_finite() or amount != amount.to_integral_value():
                raise ValueError("Invalid amount precision.")
            payload[key] = int(amount)
        else:
            payload[key] = value
    return payload


def _workspace(
    request: Request, db: Session, slug: str, *, edit: bool = False
) -> tuple[Workspace, str]:
    workspace = workspace_or_404(db, slug)
    role = (require_workspace_review if edit else require_workspace_view)(request, db, workspace.id)
    return workspace, role


@router.get("/workspaces/{workspace_slug}/intelligence", response_class=HTMLResponse)
def intelligence(
    request: Request, workspace_slug: str, db: Annotated[Session, Depends(get_db)]
) -> HTMLResponse:
    workspace, role = _workspace(request, db, workspace_slug)
    report = IntelligenceService(db).report(workspace.id)
    return templates.TemplateResponse(
        request,
        "intelligence.html",
        page_context(
            request,
            title=f"{workspace.name} · Decisions",
            workspace=workspace,
            report=report,
            can_edit=role in {"platform_admin", "owner", "admin"},
            answer=None,
        ),
    )


@router.get("/portfolio", response_class=HTMLResponse)
def portfolio(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    offset: int = Query(default=0, ge=0, le=10_000),
) -> HTMLResponse:
    workspaces, total = WorkspaceRepository(db).list_workspaces(
        accessible_workspace_ids(request, db), 10, offset
    )
    cards = []
    for workspace in workspaces:
        report = IntelligenceService(db).report(workspace.id)
        cards.append({"workspace": workspace, "report": report})
    return templates.TemplateResponse(
        request,
        "intelligence_portfolio.html",
        page_context(request, title="Portfolio", cards=cards, total=total, offset=offset),
    )


@router.get("/workspaces/{workspace_slug}/intelligence/edit/{kind}", response_class=HTMLResponse)
def edit_context(
    request: Request,
    workspace_slug: str,
    kind: RecordKind,
    db: Annotated[Session, Depends(get_db)],
    record_id: int | None = Query(default=None, ge=1),
    recommendation: str | None = Query(default=None, max_length=96),
) -> HTMLResponse:
    workspace, _role = _workspace(request, db, workspace_slug, edit=True)
    repository = IntelligenceRepository(db)
    record = None
    if record_id:
        try:
            record = repository.get(workspace.id, record_id)
        except ContextNotFound:
            raise HTTPException(status_code=404, detail="business record not found") from None
        if record.kind != kind.value:
            raise HTTPException(status_code=404, detail="business record not found")
    elif kind == RecordKind.STRATEGY:
        record = repository.strategy(workspace.id)
    data = dict(record.data) if record else {}
    if kind == RecordKind.DECISION and record is None:
        report = IntelligenceService(db).report(workspace.id)
        suggestion = next(
            (r for r in report["recommendations"] if r["key"] == recommendation), None
        )
        if suggestion is None:
            raise HTTPException(status_code=404, detail="recommendation not found")
        data = {
            "title": suggestion["title"],
            "recommendation_key": suggestion["key"],
            "evidence_fingerprint": suggestion["evidence_fingerprint"],
            "review_on": suggestion["review_on"],
            "expected_result": suggestion["expected_result"],
        }
    return templates.TemplateResponse(
        request,
        "intelligence_form.html",
        page_context(
            request,
            title=f"{kind.value.title()} · {workspace.name}",
            workspace=workspace,
            kind=kind.value,
            description=DESCRIPTIONS[kind.value],
            record=record,
            data=data,
            fields=_fields(kind, data),
            campaigns=IntelligenceService(db).campaign_options(workspace.id),
        ),
    )


@router.post("/workspaces/{workspace_slug}/intelligence/save/{kind}")
async def save_form(
    request: Request, workspace_slug: str, kind: RecordKind, db: Annotated[Session, Depends(get_db)]
) -> Response:
    workspace, role = _workspace(request, db, workspace_slug, edit=True)
    form = dict(await request.form())
    request.scope["_form"] = form
    validate_csrf(request)
    record_id = None
    version = 0
    error: HTTPException | None = None
    try:
        payload = _form_payload(kind, form)
        record_id = int(str(form["record_id"])) if form.get("record_id") else None
        version = int(str(form.get("expected_version", 0)))
        if record_id and kind == RecordKind.DECISION:
            previous = IntelligenceRepository(db).get(workspace.id, record_id)
            payload["evidence_snapshot"] = previous.data.get("evidence_snapshot", {})
        command = SaveRecord(expected_version=version, payload=payload)
        save_context(db, workspace.id, kind, command, actor_role=role, record_id=record_id)
    except ContextNotFound:
        raise HTTPException(status_code=404, detail="business record not found") from None
    except (ValueError, InvalidOperation, ValidationError):
        error = HTTPException(
            status_code=422, detail="invalid business context; check the form values"
        )
    except HTTPException as exc:
        if exc.status_code not in {409, 422}:
            raise
        error = exc
    if error:
        fields = _fields(kind, {})
        for field in fields:
            field["value"] = str(form.get(field["name"], ""))
        return templates.TemplateResponse(
            request,
            "intelligence_form.html",
            page_context(
                request,
                title=f"{kind.value.title()} · {workspace.name}",
                workspace=workspace,
                kind=kind.value,
                description=DESCRIPTIONS[kind.value],
                record={"id": record_id, "version": version} if record_id else None,
                data=form,
                fields=fields,
                error=error.detail,
                campaigns=IntelligenceService(db).campaign_options(workspace.id),
            ),
            status_code=error.status_code,
        )
    return RedirectResponse(
        url=f"/dashboard/workspaces/{workspace.slug}/intelligence", status_code=303
    )


@router.post("/workspaces/{workspace_slug}/intelligence/restore/{revision_id}")
async def restore_context(
    request: Request, workspace_slug: str, revision_id: int, db: Annotated[Session, Depends(get_db)]
) -> RedirectResponse:
    workspace, role = _workspace(request, db, workspace_slug, edit=True)
    form = dict(await request.form())
    request.scope["_form"] = form
    validate_csrf(request)
    try:
        IntelligenceRepository(db).restore_strategy(
            workspace.id, revision_id, int(str(form.get("expected_version", -1))), role
        )
        db.commit()
    except ContextNotFound:
        db.rollback()
        raise HTTPException(status_code=404, detail="strategy revision not found") from None
    except ContextConflict:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="strategy changed; reload before restoring"
        ) from None
    except (ValueError, ValidationError):
        db.rollback()
        raise HTTPException(status_code=422, detail="invalid strategy revision") from None
    return RedirectResponse(
        url=f"/dashboard/workspaces/{workspace.slug}/intelligence", status_code=303
    )


@router.post("/workspaces/{workspace_slug}/intelligence/ask", response_class=HTMLResponse)
async def ask_analyst(
    request: Request, workspace_slug: str, db: Annotated[Session, Depends(get_db)]
) -> HTMLResponse:
    workspace, role = _workspace(request, db, workspace_slug)
    form = dict(await request.form())
    request.scope["_form"] = form
    validate_csrf(request)
    try:
        question = AnalystQuestion(question=str(form.get("question", "")))
    except ValidationError:
        raise HTTPException(
            status_code=422, detail="enter a question of 1 to 500 characters"
        ) from None
    service = IntelligenceService(db)
    report = service.report(workspace.id)
    answer = service.answer(report, question.question)
    return templates.TemplateResponse(
        request,
        "intelligence.html",
        page_context(
            request,
            title=f"{workspace.name} · Decisions",
            workspace=workspace,
            report=report,
            can_edit=role in {"platform_admin", "owner", "admin"},
            answer=answer,
        ),
    )


@router.post("/workspaces/{workspace_slug}/intelligence/scenario", response_class=HTMLResponse)
async def model_budget(
    request: Request, workspace_slug: str, db: Annotated[Session, Depends(get_db)]
) -> HTMLResponse:
    workspace, role = _workspace(request, db, workspace_slug)
    form = dict(await request.form())
    request.scope["_form"] = form
    validate_csrf(request)
    service = IntelligenceService(db)
    report = service.report(workspace.id)
    try:
        amount = Decimal(str(form.get("proposed_budget", ""))) * 1_000_000
        if not amount.is_finite() or amount != amount.to_integral_value():
            raise ValueError("Invalid budget precision.")
        command = ScenarioRequest(
            proposed_budget_micros=int(amount),
            response_elasticity=Decimal(str(form.get("response_elasticity", "0.7"))),
            uncertainty_bps=3000,
        )
        scenario = service.scenario(report, command)
    except (ValueError, InvalidOperation, ValidationError):
        raise HTTPException(
            status_code=422, detail="check the budget and response assumption"
        ) from None
    scenario["label"] = "Your custom scenario"
    report["scenarios"].append(scenario)
    return templates.TemplateResponse(
        request,
        "intelligence.html",
        page_context(
            request,
            title=f"{workspace.name} · Budget scenario",
            workspace=workspace,
            report=report,
            can_edit=role in {"platform_admin", "owner", "admin"},
            answer=None,
        ),
    )


def _csv_cell(value: object) -> str:
    text = str(value) if value is not None else ""
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


@router.get("/workspaces/{workspace_slug}/intelligence/brief.csv")
def export_brief(
    request: Request, workspace_slug: str, db: Annotated[Session, Depends(get_db)]
) -> Response:
    workspace, _role = _workspace(request, db, workspace_slug)
    report = IntelligenceService(db).report(workspace.id)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["Workspace", "As of", "Priority", "Action", "Evidence", "Next step", "Review on"]
    )
    for item in report["recommendations"]:
        writer.writerow(
            [
                _csv_cell(value)
                for value in (
                    workspace.name,
                    report["as_of"],
                    item["priority"],
                    item["title"],
                    item["evidence"],
                    item["action"],
                    item["review_on"],
                )
            ]
        )
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="ad-analyzer-brief.csv"'},
    )
