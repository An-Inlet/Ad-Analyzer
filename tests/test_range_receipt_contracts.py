from datetime import UTC, datetime, timedelta

import pytest
from app.campaign_performance.range_receipt_contracts import RangeReceiptV1
from pydantic import ValidationError

from tests.test_selected_raw_observations import google_request


def receipt() -> RangeReceiptV1:
    dep = google_request().aggregate
    return RangeReceiptV1(
        request_id="a" * 32,
        initiating_customer_id="b" * 32,
        requested_starts_on=dep.starts_on,
        requested_ends_on=dep.ends_on,
        original_scope=dep.scope,
        final_scope=dep.scope,
        completion_id=dep.completion_id,
        manifest_digest=dep.manifest_digest,
        query_version="google.v24.campaign-day.metrics-conversions.v1",
        completed_at=datetime.combine(dep.ends_on + timedelta(days=2), datetime.min.time(), UTC),
        row_count=0,
        acquisition_digest="c" * 64,
        job_id=1,
    )


def test_strict_receipt_roundtrip() -> None:
    value = receipt()
    assert RangeReceiptV1.model_validate_json(value.model_dump_json()) == value
    assert RangeReceiptV1.model_validate_json(value.model_dump_json()).digest() == value.digest()


@pytest.mark.parametrize("kind", ["privacy", "scope", "future", "query", "bool"])
def test_receipt_rejects_changed_scope_or_unqualified_metadata(kind: str) -> None:
    value = receipt().model_dump(mode="json")
    if kind == "privacy":
        value["original_scope"]["privacy_revision"] += 1
    elif kind == "scope":
        value["final_scope"]["generation"] += 1
    elif kind == "future":
        value["requested_ends_on"] = "2099-01-01"
    elif kind == "query":
        value["query_version"] = "google.v25.other"
    else:
        value["row_count"] = True
    import json

    with pytest.raises(ValidationError):
        RangeReceiptV1.model_validate_json(json.dumps(value))
