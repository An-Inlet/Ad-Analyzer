"""Q07 currency evidence from original bootstrap, never mutated retained receipts."""

from sqlalchemy import Engine

from tests.creative_q05_fixture import CreativeQ05Basis


def assert_owned_eur_selector(q05: CreativeQ05Basis) -> None:
    # Actual catalog currency is asserted during Q05 acquisition for this explicit variant.
    assert q05.selectors[1]["account_id"] == q05.account_ids[1]
    assert q05.account_ids[1] in q05.body["inputs"]["account_ids"]


def planning_snapshot(engine: Engine) -> tuple[tuple[str, ...], ...]:
    """Exact retained rows, including request receipts; no baseline deletion exemption."""
    from app.planning_documents.models import (
        PlanDependencyRow,
        PlanEventRow,
        PlanInputRow,
        PlanRequestRow,
        PlanRow,
        PlanVersionRow,
    )
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    with Session(engine) as db:
        return tuple(
            tuple(sorted(repr(dict(row)) for row in db.execute(select(model.__table__)).mappings()))
            for model in (
                PlanRow,
                PlanInputRow,
                PlanVersionRow,
                PlanDependencyRow,
                PlanEventRow,
                PlanRequestRow,
            )
        )
