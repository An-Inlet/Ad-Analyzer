"""Snapshot-local complete graph export; no current-source or original-session lookup."""

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.campaign_performance.models import PerformanceCompletion
from app.campaign_performance.presence_contracts import (
    ReportedMetricPresenceV1,
    ReportingSemanticsV1,
)
from app.campaign_performance.presence_models import MetricPresenceRow, ReportingSemanticsRow
from app.campaign_performance.presence_storage import (
    ReportingPresenceUnavailable,
    _row,
    read_presence,
)


class PresenceExportContext:
    """One read-only export operation/transaction, caching at most one complete graph."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.transaction = db.get_transaction()
        self.completion_id: str | None = None
        self.rows: dict[tuple[Any, ...], dict[str, Any]] = {}

    def export(self, table: str, supplied: Mapping[str, Any]) -> dict[str, Any]:
        from app.lifecycle.inventory import scalar

        current = self.db.get_transaction()
        if current is None or self.transaction is not current or not current.is_active:
            raise ReportingPresenceUnavailable("presence export transaction changed")
        completion_id = supplied["completion_id"]
        if completion_id != self.completion_id:
            self.rows = {}
            completion = self.db.get(PerformanceCompletion, completion_id, populate_existing=True)
            if completion is None:
                raise ReportingPresenceUnavailable("presence export completion missing")
            result = read_presence(self.db, completion)
            if result is None:
                raise ReportingPresenceUnavailable("presence export graph missing")
            header, facts = result
            documents: list[tuple[str, ReportingSemanticsV1 | ReportedMetricPresenceV1]] = [
                (ReportingSemanticsRow.__tablename__, header),
                *((MetricPresenceRow.__tablename__, f) for f in facts),
            ]
            for name, document in documents:
                values = _row(document)
                key: tuple[Any, ...] = (name, completion_id)
                if name == MetricPresenceRow.__tablename__:
                    key += (values["campaign_id"], scalar(values["metric_date"]))
                self.rows[key] = {**values, "document": document.model_dump(mode="json")}
            self.completion_id = completion_id
        key = (table, completion_id)
        if table == MetricPresenceRow.__tablename__:
            key += (supplied["campaign_id"], scalar(supplied["metric_date"]))
        expected = self.rows.get(key)
        if expected is None or any(
            key not in supplied or scalar(supplied[key]) != scalar(value)
            for key, value in expected.items()
            if key != "document"
        ):
            raise ReportingPresenceUnavailable("presence export row mismatch")
        return {
            key: value if key == "document" else scalar(value)
            for key, value in expected.items()
            if key != "canonical_json"
        }
