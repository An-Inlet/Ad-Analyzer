"""Pure strict-guard negatives: sentinel rows are not persisted authority."""

from typing import Any, cast

import pytest
from sqlalchemy import Engine

from tests import reported_planning_original_fixture as fixture
from tests.reported_original_fixture import RetainedReportedOriginalIds


@pytest.mark.parametrize(
    "present", ["initial_budget_mandate_preparations", "initial_planning_consents"]
)
def test_unbound_expectation_rejects_planning_rows(
    present: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No database write or fabricated consent: only the guard's count query result.
    class Counts:
        def __enter__(self) -> "Counts":
            return self

        def __exit__(self, *args: Any) -> None:
            pass

        def scalar(self, statement: Any) -> int:
            return int(statement.get_final_froms()[0].name == present)

    monkeypatch.setattr(fixture, "effect_graph", lambda _: {})
    monkeypatch.setattr(fixture, "Session", lambda _: Counts())
    # Neither value is dereferenced by an unbound guard; no fake identity is accepted.
    with pytest.raises(AssertionError):
        fixture.ExpectedPlanningConfirmation().assert_delta(
            cast(Engine, object()), cast(RetainedReportedOriginalIds, object()), {}
        )
