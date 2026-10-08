from datetime import UTC, datetime
from typing import Any

import pytest
from app.goals.progress_contracts import GoalSalesProgressV1
from app.planning_documents.documents import PlanVersion
from app.planning_documents.progress_contracts import PlanSalesProgressV1, project_sales_progress
from app.publication.contracts import fingerprint
from pydantic import ValidationError

from tests.test_planning_document_contracts import packet


def sample(amount: int | None = 0) -> tuple[PlanVersion, GoalSalesProgressV1]:
    document = PlanVersion.model_validate(packet())
    ref = document.inputs.goal
    definition = ref.definition
    sales = GoalSalesProgressV1(
        workspace_id=ref.workspace_id,
        goal_id=ref.goal_id,
        revision=ref.revision,
        definition_digest=fingerprint(
            "inlet.goal-progress-definition.v1", definition.model_dump(mode="json")
        ),
        status="available_as_of" if amount is not None else "unavailable",
        target_window=definition.target_window,
        target_micros=definition.target_micros,
        store_id=definition.store_id,
        currency="USD",
        time_zone="UTC",
        coverage=dict(
            starts_on="2026-10-01",
            ends_on_exclusive="2026-10-07",
            starts_at="2026-10-01T00:00:00Z",
            ends_at_exclusive="2026-10-07T00:00:00Z",
            closed_day_count=6,
            extent="partial_period",
        ),
        net_sales_micros=amount,
        source_watermark=datetime(2026, 10, 7, 12, tzinfo=UTC),
        source_revision=1,
        import_in_progress=False,
        as_of=datetime(2026, 10, 7, 13, tzinfo=UTC),
        reasons=() if amount is not None else ("missing_history",),
    )
    return document, sales


@pytest.mark.parametrize("amount", [None, 0, -1, 1, 2**53 + 1, -(2**53 + 1), 10**30, -(10**30)])
def test_exact_signed_wire_projection(amount: int | None) -> None:
    document, sales = sample(amount)
    value = project_sales_progress(document, sales=sales, reason=None, as_of=sales.as_of)
    assert value.net_sales_micros_exact == (str(amount) if amount is not None else None)
    assert value.document_digest == document.digest() and value.goal == document.inputs.goal
    assert value.model_dump(mode="json")["net_sales_micros_exact"] == value.net_sales_micros_exact
    assert not value.advertising_writes_enabled and value.manual_application == "not_assessed"
    payload = value.model_dump(exclude={"net_sales_micros_exact"})
    with pytest.raises(ValidationError):
        PlanSalesProgressV1.model_validate({**payload, "net_sales_micros_exact": "1"})


@pytest.mark.parametrize(
    "field,value",
    [
        ("revision", 2),
        ("workspace_id", 2),
        ("goal_id", "f" * 32),
        ("store_id", "f" * 32),
        ("target_micros", 999),
        ("definition_digest", "f" * 64),
        ("spending_authorized", True),
        ("net_sales_micros", True),
        ("net_sales_micros", 1.5),
    ],
)
def test_unsafe_nested_sales_copy_rejected(field: str, value: Any) -> None:
    document, sales = sample(1)
    unsafe = sales.model_copy(update={field: value})
    with pytest.raises(ValidationError):
        project_sales_progress(document, sales=unsafe, reason=None, as_of=sales.as_of)


def test_unsafe_nested_coverage_and_goal_copy_rejected() -> None:
    document, sales = sample()
    assert sales.coverage
    unsafe = sales.model_copy(
        update={"coverage": sales.coverage.model_copy(update={"closed_day_count": 7})}
    )
    with pytest.raises(ValidationError):
        project_sales_progress(document, sales=unsafe, reason=None, as_of=sales.as_of)
    invalid = document.model_copy(
        update={
            "inputs": document.inputs.model_copy(
                update={"goal": document.inputs.goal.model_copy(update={"revision": True})}
            )
        }
    )
    with pytest.raises(ValidationError):
        project_sales_progress(invalid, sales=sales, reason=None, as_of=sales.as_of)


def test_unavailable_no_amount_or_replacement_definition() -> None:
    document, sales = sample(10)
    value = project_sales_progress(document, sales=None, reason="goal_changed", as_of=sales.as_of)
    assert value.sales is None and value.net_sales_micros_exact is None
    assert value.goal == document.inputs.goal
    with pytest.raises(ValidationError):
        project_sales_progress(document, sales=sales, reason="goal_changed", as_of=sales.as_of)
    with pytest.raises(ValidationError):
        project_sales_progress(document, sales=None, reason=None, as_of=sales.as_of)
    with pytest.raises(ValidationError):
        project_sales_progress(
            document,
            sales=sales.model_copy(
                update={"definition_digest": document.inputs.goal.definition_digest}
            ),
            reason=None,
            as_of=sales.as_of,
        )
