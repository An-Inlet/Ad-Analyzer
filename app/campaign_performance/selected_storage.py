"""Internal transaction ports. No session, catalog, provider or spending authority."""

import hashlib
import json
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount, Campaign
from app.campaign_performance.models import PerformanceCompletion
from app.campaign_performance.selected_contracts import (
    MAX_SELECTED_FACTS,
    AggregateDependencyV1,
    CustomerEventSelectionV1,
    ReportingScopeV1,
    SelectedCampaignDayV1,
    SelectedCaptureV1,
    selected_capture_digest,
    selection_digest,
    validate_selected_dependencies,
)
from app.campaign_performance.selected_models import (
    CurrentEventSelectionRow,
    EventSelectionRow,
    SelectedCaptureRow,
    SelectedFactRow,
)
from app.campaign_performance.service import read_current, require_active_integration
from app.customers.models import CustomerMembership, CustomerUser
from app.google_connections.models import GoogleCustomerConnection
from app.lifecycle.privacy import workspace_export_revision
from app.meta.models import MetaConnection
from app.sources.models import SourceConnection
from app.workspaces.models import Workspace

MODELS = (EventSelectionRow, CurrentEventSelectionRow, SelectedCaptureRow, SelectedFactRow)
TABLES = frozenset(m.__tablename__ for m in MODELS)


class SelectedReportingUnavailable(ValueError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def hashed(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def lock_scope(db: Session, wid: int, aid: int) -> AdvertisingAccount:
    workspace = db.scalar(
        select(Workspace)
        .where(Workspace.id == wid)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    account = db.scalar(
        select(AdvertisingAccount)
        .where(AdvertisingAccount.id == aid, AdvertisingAccount.workspace_id == wid)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if workspace is None or account is None:
        raise SelectedReportingUnavailable("selected ownership unavailable")
    return account


def current_scope(db: Session, scope: ReportingScopeV1) -> None:
    account = lock_scope(db, scope.workspace_id, scope.account_id)
    workspace = db.get(Workspace, scope.workspace_id, populate_existing=True)
    require_active_integration(db, account)
    model: Any = {
        "google_ads": GoogleCustomerConnection,
        "meta_ads": MetaConnection,
        "tiktok_ads": SourceConnection,
    }[scope.platform]
    query = select(model).where(
        model.workspace_id == scope.workspace_id, model.account_id == scope.account_id
    )
    if scope.platform == "tiktok_ads":
        query = query.where(SourceConnection.provider == "tiktok_ads")
    sources = list(
        db.scalars(query.with_for_update().execution_options(populate_existing=True)).all()
    )
    if len(sources) != 1:
        raise SelectedReportingUnavailable("selected source unavailable")
    source = sources[0]
    native = source.external_id if scope.platform == "tiktok_ads" else source.external_account_id
    integration = (
        source.workspace_integration_id if scope.platform == "meta_ads" else source.integration_id
    )
    if (
        workspace is None
        or workspace.status != "active"
        or (
            account.connection_id,
            account.platform.value,
            account.external_account_id,
            account.currency_code,
            account.time_zone,
        )
        != (
            scope.connection_id,
            scope.platform,
            scope.native_account_id,
            scope.currency,
            scope.time_zone,
        )
        or (str(source.id), source.generation, source.status, native, integration)
        != (
            scope.source_connection_ref,
            scope.generation,
            "connected",
            scope.native_account_id,
            scope.connection_id,
        )
        or source.error_code
        or workspace_export_revision(db, scope.workspace_id) != scope.privacy_revision
    ):
        raise SelectedReportingUnavailable("selected scope changed")


def _selection(row: EventSelectionRow) -> CustomerEventSelectionV1:
    value = CustomerEventSelectionV1.model_validate_json(row.canonical_json)
    if selection_values(value) != {k: getattr(row, k) for k in selection_values(value)}:
        raise SelectedReportingUnavailable("selection integrity unavailable")
    return value


def selection_values(value: CustomerEventSelectionV1) -> dict[str, Any]:
    raw = canonical(value.model_dump(mode="json"))
    if len(raw.encode()) > 8192:
        raise SelectedReportingUnavailable("selection capacity exceeded")
    return dict(
        id=value.selection_id,
        workspace_id=value.scope.workspace_id,
        account_id=value.scope.account_id,
        connection_id=value.scope.connection_id,
        confirmed_by_customer_id=value.confirmed_by_customer_id,
        canonical_json=raw,
        payload_digest=selection_digest(value),
        payload_bytes=len(raw.encode()),
    )


def read_selection(db: Session, workspace_id: int, account_id: int) -> CustomerEventSelectionV1:
    lock_scope(db, workspace_id, account_id)
    head = db.get(CurrentEventSelectionRow, account_id, populate_existing=True)
    if head is None or head.workspace_id != workspace_id or head.invalidated:
        raise SelectedReportingUnavailable("selection unavailable")
    row = db.get(EventSelectionRow, head.selection_id, populate_existing=True)
    if row is None or (row.account_id, row.workspace_id, row.connection_id, row.payload_digest) != (
        account_id,
        workspace_id,
        head.connection_id,
        head.selection_digest,
    ):
        raise SelectedReportingUnavailable("selection head changed")
    value = _selection(row)
    current_scope(db, value.scope)
    return value


def store_selection(
    db: Session,
    selection: CustomerEventSelectionV1,
    expected_selection_id: str | None,
    expected_selection_digest: str | None,
) -> CustomerEventSelectionV1:
    value = CustomerEventSelectionV1.model_validate(selection)
    current_scope(db, value.scope)
    owner = db.scalar(
        select(CustomerMembership)
        .where(
            CustomerMembership.workspace_id == value.scope.workspace_id,
            CustomerMembership.user_id == value.confirmed_by_customer_id,
        )
        .execution_options(populate_existing=True)
    )
    user = db.get(CustomerUser, value.confirmed_by_customer_id, populate_existing=True)
    if (
        owner is None
        or owner.status != "active"
        or owner.role != "owner"
        or user is None
        or user.status != "active"
    ):
        raise SelectedReportingUnavailable("confirming owner unavailable")
    head = db.get(CurrentEventSelectionRow, value.scope.account_id, populate_existing=True)
    existing = db.get(EventSelectionRow, value.selection_id, populate_existing=True)
    if existing is not None:
        if _selection(existing) != value:
            raise SelectedReportingUnavailable("selection replay differs")
        if (
            head is not None
            and not head.invalidated
            and head.selection_id == value.selection_id
            and head.selection_digest == selection_digest(value)
        ):
            return read_selection(db, value.scope.workspace_id, value.scope.account_id)
        raise SelectedReportingUnavailable("selection cannot be readopted")
    expected = (expected_selection_id, expected_selection_digest)
    actual = (head.selection_id, head.selection_digest) if head else (None, None)
    if expected != actual:
        raise SelectedReportingUnavailable("selection compare-and-swap conflict")
    from app.initial_planning.models import CalibrationRow

    if head is not None and not head.invalidated:
        raise SelectedReportingUnavailable("selection invalidation and aggregate refresh required")

    if head and (
        db.scalar(
            select(SelectedCaptureRow.id)
            .where(SelectedCaptureRow.account_id == value.scope.account_id)
            .limit(1)
        )
        is not None
        or db.scalar(
            select(CalibrationRow.id)
            .where(CalibrationRow.account_id == value.scope.account_id)
            .limit(1)
        )
        is not None
    ):
        raise SelectedReportingUnavailable("selection invalidation and aggregate refresh required")
    with db.begin_nested():
        db.add(EventSelectionRow(**selection_values(value)))
        db.flush()
        if head is None:
            db.add(
                CurrentEventSelectionRow(
                    workspace_id=value.scope.workspace_id,
                    account_id=value.scope.account_id,
                    connection_id=value.scope.connection_id,
                    selection_id=value.selection_id,
                    selection_digest=selection_digest(value),
                )
            )
        else:
            head.selection_id, head.selection_digest = value.selection_id, selection_digest(value)
            head.invalidated = False
        db.flush()
    return value


def _aggregate(db: Session, dependency: AggregateDependencyV1) -> None:
    scope = dependency.scope
    current_scope(db, scope)
    campaign = db.scalar(
        select(Campaign.id)
        .where(Campaign.account_id == scope.account_id)
        .order_by(Campaign.id)
        .limit(1)
    )
    if campaign is None:
        raise SelectedReportingUnavailable("aggregate campaign unavailable")

    # Storage validates ownership/source here, not an invented customer session.
    def check(session: Session, wid: int, actor: str) -> None:
        if wid != scope.workspace_id or actor != "internal-storage":
            raise SelectedReportingUnavailable("aggregate scope changed")
        current_scope(session, scope)

    read_current(
        db,
        scope.workspace_id,
        "internal-storage",
        scope.account_id,
        campaign,
        dependency.completion_id,
        check,
    )
    row = db.get(PerformanceCompletion, dependency.completion_id, populate_existing=True)
    if row is None or (
        row.workspace_id,
        row.account_id,
        row.manifest_digest,
        row.starts_on,
        row.ends_on,
        row.generation,
        row.privacy_revision,
    ) != (
        scope.workspace_id,
        scope.account_id,
        dependency.manifest_digest,
        dependency.starts_on,
        dependency.ends_on,
        scope.generation,
        scope.privacy_revision,
    ):
        raise SelectedReportingUnavailable("aggregate dependency changed")


def capture_values(value: SelectedCaptureV1) -> dict[str, Any]:
    body = value.model_dump(mode="json", exclude={"facts"})
    raw = canonical(body)
    r = value.request
    return dict(
        id=r.capture_id,
        workspace_id=r.aggregate.scope.workspace_id,
        account_id=r.aggregate.scope.account_id,
        connection_id=r.aggregate.scope.connection_id,
        selection_id=r.selection.selection_id,
        selection_digest=r.selection_digest,
        completion_id=r.aggregate.completion_id,
        request_digest=value.request_digest,
        fact_count=len(value.facts),
        canonical_json=raw,
        payload_digest=selected_capture_digest(value),
        payload_bytes=len(raw.encode()),
    )


def fact_values(value: SelectedCampaignDayV1, wid: int, aid: int) -> dict[str, Any]:
    raw = canonical(value.model_dump(mode="json"))
    return dict(
        capture_id=value.capture_id,
        campaign_id=value.campaign_id,
        metric_date=value.metric_date,
        workspace_id=wid,
        account_id=aid,
        native_campaign_id=value.native_campaign_id,
        canonical_json=raw,
        payload_digest=hashed(raw),
        payload_bytes=len(raw.encode()),
    )


def _reconstruct_capture(
    header: SelectedCaptureRow,
    rows: list[SelectedFactRow],
    campaigns: dict[int, Campaign],
    wid: int,
    aid: int,
) -> SelectedCaptureV1:
    """Pure reconstruction at the original position, before dependency SQL."""
    body = json.loads(header.canonical_json)
    facts = []
    measured = len(header.canonical_json.encode())
    for row in rows:
        measured += row.payload_bytes
        if measured > 32 * 1024 * 1024:
            raise SelectedReportingUnavailable("selected capture byte bound exceeded")
        fact = SelectedCampaignDayV1.model_validate_json(row.canonical_json)
        if fact_values(fact, wid, aid) != {k: getattr(row, k) for k in fact_values(fact, wid, aid)}:
            raise SelectedReportingUnavailable("selected fact integrity unavailable")
        campaign = campaigns.get(fact.campaign_id)
        if campaign is None or (
            campaign.account_id,
            campaign.external_campaign_id,
            campaign.platform.value,
        ) != (
            aid,
            fact.native_campaign_id,
            body["request"]["aggregate"]["scope"]["platform"],
        ):
            raise SelectedReportingUnavailable("selected campaign changed")
        facts.append(fact.model_dump(mode="json"))
    body = json.loads(header.canonical_json)
    body["facts"] = facts
    value = SelectedCaptureV1.model_validate_json(canonical(body))
    if capture_values(value) != {k: getattr(header, k) for k in capture_values(value)}:
        raise SelectedReportingUnavailable("selected capture integrity unavailable")
    return value


def historical_capture(db: Session, wid: int, aid: int, capture_id: str) -> SelectedCaptureV1:
    header = db.get(SelectedCaptureRow, capture_id, populate_existing=True)
    if header is None or (header.workspace_id, header.account_id) != (wid, aid):
        raise SelectedReportingUnavailable("selected capture unavailable")
    rows = list(
        db.scalars(
            select(SelectedFactRow)
            .where(SelectedFactRow.capture_id == capture_id)
            .order_by(SelectedFactRow.campaign_id, SelectedFactRow.metric_date)
            .limit(MAX_SELECTED_FACTS + 1)
            .execution_options(populate_existing=True)
        )
    )
    if len(rows) != header.fact_count or len(rows) > MAX_SELECTED_FACTS:
        raise SelectedReportingUnavailable("selected facts incomplete")
    campaigns = {
        c.id: c
        for c in db.scalars(
            select(Campaign)
            .join(SelectedFactRow, SelectedFactRow.campaign_id == Campaign.id)
            .where(SelectedFactRow.capture_id == capture_id)
            .distinct()
            .limit(MAX_SELECTED_FACTS + 1)
            .execution_options(populate_existing=True)
        )
    }
    from app.campaign_performance.selected_reconstruction import reconstruct

    value, promote = reconstruct(db, header, rows, campaigns, wid, aid, _reconstruct_capture)
    selection = db.get(EventSelectionRow, header.selection_id, populate_existing=True)
    completion = db.get(PerformanceCompletion, header.completion_id, populate_existing=True)
    dep = value.request.aggregate
    if (
        selection is None
        or _selection(selection) != value.request.selection
        or completion is None
        or (
            completion.workspace_id,
            completion.account_id,
            completion.manifest_digest,
            completion.starts_on,
            completion.ends_on,
            completion.generation,
            completion.privacy_revision,
            completion.platform,
            completion.source_connection_ref,
            completion.currency,
            completion.time_zone,
        )
        != (
            wid,
            aid,
            dep.manifest_digest,
            dep.starts_on,
            dep.ends_on,
            dep.scope.generation,
            dep.scope.privacy_revision,
            dep.scope.platform,
            dep.scope.source_connection_ref,
            dep.scope.currency,
            dep.scope.time_zone,
        )
    ):
        raise SelectedReportingUnavailable("selected historical dependency unavailable")
    promote()
    return value


def read_selected_capture(
    db: Session, workspace_id: int, account_id: int, capture_id: str
) -> SelectedCaptureV1:
    lock_scope(db, workspace_id, account_id)
    value = historical_capture(db, workspace_id, account_id, capture_id)
    selection = read_selection(db, workspace_id, account_id)
    _aggregate(db, value.request.aggregate)
    validate_selected_dependencies(value, value.request.aggregate, selection)
    return value


def store_selected_capture(db: Session, capture: SelectedCaptureV1) -> None:
    value = SelectedCaptureV1.model_validate(capture)
    s = value.request.aggregate.scope
    current = read_selection(db, s.workspace_id, s.account_id)
    _aggregate(db, value.request.aggregate)
    validate_selected_dependencies(value, value.request.aggregate, current)
    existing = db.get(SelectedCaptureRow, value.request.capture_id, populate_existing=True)
    if existing is not None:
        prior = read_selected_capture(db, s.workspace_id, s.account_id, value.request.capture_id)
        if selected_capture_digest(prior) != selected_capture_digest(value):
            raise SelectedReportingUnavailable("selected replay differs")
        return
    with db.begin_nested():
        db.add(SelectedCaptureRow(**capture_values(value)))
        db.flush()
        for fact in value.facts:
            campaign = db.get(Campaign, fact.campaign_id, populate_existing=True)
            if campaign is None or (
                campaign.account_id,
                campaign.external_campaign_id,
                campaign.platform.value,
            ) != (s.account_id, fact.native_campaign_id, s.platform):
                raise SelectedReportingUnavailable("selected campaign mapping changed")
            db.add(SelectedFactRow(**fact_values(fact, s.workspace_id, s.account_id)))
        db.flush()
        historical_capture(db, s.workspace_id, s.account_id, value.request.capture_id)


def invalidate_selected_account(db: Session, workspace_id: int, account_id: int) -> None:
    """Commit this transition before genuine refresh/reconfirmation; never relabel."""
    lock_scope(db, workspace_id, account_id)
    head = db.get(CurrentEventSelectionRow, account_id, populate_existing=True)
    if head is None or head.invalidated:
        return
    head.invalidated = True
    db.flush()  # DB transition erases captures/calibrations and advances existing fence.


def erase_workspace_selected(db: Session, workspace_id: int) -> None:
    """Semantic privacy hook, including closing workspaces; caller holds workspace."""
    db.execute(delete(SelectedCaptureRow).where(SelectedCaptureRow.workspace_id == workspace_id))
    db.execute(
        delete(CurrentEventSelectionRow).where(
            CurrentEventSelectionRow.workspace_id == workspace_id
        )
    )
    db.execute(delete(EventSelectionRow).where(EventSelectionRow.workspace_id == workspace_id))


# Replaying a pure result is disabled if its reconstruction helpers are replaced.
_PURE_RECONSTRUCTION = tuple(
    (name, globals()[name])
    for name in (
        "_reconstruct_capture",
        "canonical",
        "hashed",
        "capture_values",
        "fact_values",
        "selected_capture_digest",
    )
)
