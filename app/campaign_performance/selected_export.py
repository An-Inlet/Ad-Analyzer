"""Strict historical graph export, never an assertion of current selection/capture."""

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.campaign_performance.selected_models import (
    CurrentEventSelectionRow,
    EventSelectionRow,
    SelectedCaptureRow,
    SelectedFactRow,
)
from app.campaign_performance.selected_storage import (
    SelectedReportingUnavailable,
    _selection,
    historical_capture,
)


def _export_single(db: Session, table: str, supplied: Mapping[str, Any]) -> dict[str, Any]:
    from app.lifecycle.inventory import scalar

    row: Any
    wid, aid = supplied["workspace_id"], supplied["account_id"]
    if table == EventSelectionRow.__tablename__:
        row = db.get(EventSelectionRow, supplied["id"], populate_existing=True)
        if row is None:
            raise SelectedReportingUnavailable("selection export unavailable")
        document: Any = _selection(row)
    elif table == CurrentEventSelectionRow.__tablename__:
        row = db.get(CurrentEventSelectionRow, aid, populate_existing=True)
        selected = db.get(EventSelectionRow, supplied["selection_id"], populate_existing=True)
        if (
            row is None
            or selected is None
            or (
                selected.account_id,
                selected.workspace_id,
                selected.connection_id,
                selected.payload_digest,
            )
            != (aid, wid, supplied["connection_id"], supplied["selection_digest"])
        ):
            raise SelectedReportingUnavailable("selection export head unavailable")
        _selection(selected)
        document = None
    else:
        capture_id = (
            supplied["id"] if table == SelectedCaptureRow.__tablename__ else supplied["capture_id"]
        )
        capture = historical_capture(db, wid, aid, capture_id)
        if table == SelectedCaptureRow.__tablename__:
            row = db.get(SelectedCaptureRow, capture_id, populate_existing=True)
            document = capture.model_dump(mode="json", exclude={"facts"})
        elif table == SelectedFactRow.__tablename__:
            row = db.get(
                SelectedFactRow,
                (capture_id, supplied["campaign_id"], supplied["metric_date"]),
                populate_existing=True,
            )
            document = next(
                f.model_dump(mode="json")
                for f in capture.facts
                if f.campaign_id == supplied["campaign_id"]
                and scalar(f.metric_date) == scalar(supplied["metric_date"])
            )
        else:
            raise SelectedReportingUnavailable("selected export table unavailable")
    if row is None or (row.workspace_id, row.account_id) != (wid, aid):
        raise SelectedReportingUnavailable("selected export ownership unavailable")
    values = {c.name: getattr(row, c.name) for c in row.__table__.columns}
    if set(values) != set(supplied) or any(
        scalar(v) != scalar(supplied[k]) for k, v in values.items()
    ):
        raise SelectedReportingUnavailable("selected export row mismatch")
    result = {k: scalar(v) for k, v in values.items() if k != "canonical_json"}
    if document is not None:
        result["document"] = (
            document.model_dump(mode="json") if hasattr(document, "model_dump") else document
        )
    result["currentness"] = "historical_as_observed"
    return result


class SelectedExportContext:
    """One snapshot transaction, at most one fully verified capture/index in memory."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.transaction = db.get_transaction()
        self.key: tuple[int, int, str] | None = None
        self.rows: dict[tuple[Any, ...], dict[str, Any]] = {}

    def export(self, table: str, supplied: Mapping[str, Any]) -> dict[str, Any]:
        from app.campaign_performance.selected_storage import capture_values, fact_values
        from app.lifecycle.inventory import scalar

        tx = self.db.get_transaction()
        if tx is None or tx is not self.transaction or not tx.is_active:
            raise SelectedReportingUnavailable("selected export transaction changed")
        if table in {EventSelectionRow.__tablename__, CurrentEventSelectionRow.__tablename__}:
            return _export_single(self.db, table, supplied)
        capture_id = (
            supplied["id"] if table == SelectedCaptureRow.__tablename__ else supplied["capture_id"]
        )
        key = (supplied["workspace_id"], supplied["account_id"], capture_id)
        if key != self.key:
            self.rows = {}
            value = historical_capture(self.db, *key)
            self.rows[(SelectedCaptureRow.__tablename__, capture_id)] = {
                **capture_values(value),
                "document": value.model_dump(mode="json", exclude={"facts"}),
            }
            for fact in value.facts:
                self.rows[
                    (
                        SelectedFactRow.__tablename__,
                        capture_id,
                        fact.campaign_id,
                        scalar(fact.metric_date),
                    )
                ] = {**fact_values(fact, key[0], key[1]), "document": fact.model_dump(mode="json")}
            self.key = key
        rowkey: tuple[Any, ...] = (table, capture_id)
        if table == SelectedFactRow.__tablename__:
            rowkey += (supplied["campaign_id"], scalar(supplied["metric_date"]))
        expected = self.rows.get(rowkey)
        if (
            expected is None
            or set(supplied) != set(expected) - {"document"}
            or any(scalar(supplied[k]) != scalar(v) for k, v in expected.items() if k != "document")
        ):
            raise SelectedReportingUnavailable("selected export row mismatch")
        return {
            **{
                k: scalar(v) if k != "document" else v
                for k, v in expected.items()
                if k != "canonical_json"
            },
            "currentness": "historical_as_observed",
        }


def export_selected(db: Session, table: str, supplied: Mapping[str, Any]) -> dict[str, Any]:
    return SelectedExportContext(db).export(table, supplied)
