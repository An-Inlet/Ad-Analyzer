from datetime import UTC, date, datetime

import pytest
from app.commerce.independent_contracts import ScanCompletion, ScanPermit, ScanRequest
from app.outcomes.maturity import MaturityScope, ReconciledDay
from pydantic import ValidationError


def request() -> ScanRequest:
    return ScanRequest(
        acquisition_id="1" * 32,
        scope=MaturityScope(
            workspace_id=1,
            store_id="2" * 32,
            generation=1,
            privacy_epoch=1,
            goal_id="3" * 32,
            goal_revision=1,
            goal_digest="4" * 64,
            metric_definition_digest="5" * 64,
            currency="USD",
            time_zone="America/New_York",
        ),
        connection_id=1,
        connection_version="1",
        export_privacy_revision=0,
        start=date(2026, 10, 1),
        end=date(2026, 10, 2),
    )


def test_contract_cannot_claim_maturity_or_missing_complete_days() -> None:
    data = dict(
        request=request(),
        started_at=datetime(2026, 10, 3, tzinfo=UTC),
        completed_at=datetime(2026, 10, 3, tzinfo=UTC),
        orders_enumerated=0,
        agreements_enumerated=0,
        sales_enumerated=0,
        requests_completed=2,
        response_bytes=100,
        days=(
            ReconciledDay(day=date(2026, 10, 1), state="complete", value_micros=0, entry_count=0),
        ),
    )
    result = ScanCompletion.model_validate(data)
    assert result.correction_state == "unresolved"
    assert result.maturity == "unqualified"
    for change in ({"correction_state": "settled_as_of"}, {"days": ()}):
        with pytest.raises(ValidationError):
            ScanCompletion.model_validate({**data, **change})


def test_permit_redacts_secrets_and_identity() -> None:
    permit = ScanPermit.model_validate(
        dict(
            request_digest=request().request_digest,
            expires_at=datetime(2026, 10, 3, tzinfo=UTC),
            shop_domain="synthetic.myshopify.com",
            shop_id="gid://shopify/Shop/1",
            shop_key="a" * 64,
            token="synthetic-token",
            identifier_key="synthetic-key" * 4,
            active=True,
            privacy_resolved=True,
        )
    )
    assert "synthetic" not in repr(permit) + permit.model_dump_json()
