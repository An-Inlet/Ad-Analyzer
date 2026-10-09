"""Actual completion time drift advances only the current fixture's next read clock."""

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from app.settings import Settings
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests import reported_rule_current_fixture as fixture
from tests.reported_original_fixture import RetainedReportedOriginalIds
from tests.reported_original_fixture import customer_engine as customer_engine
from tests.reported_read_acquisition_fixture import prepare_reported_acquisition
from tests.reported_rule_current_fixture import reported_rule_original as reported_rule_original
from tests.test_customer_identity import customer_engine as base_customer_engine  # noqa: F401
from tests.test_shopify_sales import configuration as configuration


def test_observed_completion_clock_not_future_schedule(
    customer_engine: Engine,
    reported_rule_original: RetainedReportedOriginalIds,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepare = prepare_reported_acquisition
    follow = fixture._follow_completed_clock
    delayed: list[float] = []
    samples = []

    def actual_prepare(*args: Any, **kwargs: Any) -> Any:
        acquired = prepare(*args, **kwargs)

        def delay_fixed_terminal() -> None:
            if acquired.runner._fixed_lease is not None and not delayed:
                pause = max(0.0, (acquired.clock[0] - datetime.now(UTC)).total_seconds()) + 0.2
                assert pause <= 2
                delayed.append(pause)
                time.sleep(pause)

        acquired.control["on_insights"] = delay_fixed_terminal
        return acquired

    def observed(*args: Any, **kwargs: Any) -> int:
        acquired, _, _, result, previous = args
        before = acquired.clock[0]
        count = follow(*args, **kwargs)
        samples.append(
            (
                result["status"],
                acquired.runner._fixed_lease,
                before,
                acquired.clock[0],
                previous,
                count,
            )
        )
        return count

    monkeypatch.setattr(fixture, "prepare_reported_acquisition", actual_prepare)
    monkeypatch.setattr(fixture, "_follow_completed_clock", observed)
    with Session(customer_engine) as db:
        _, _, _, _, _, _, server = fixture.ready_current_reported_rule(
            db,
            configuration,
            tmp_path,
            monkeypatch,
            original=reported_rule_original,
            engine=customer_engine,
        )
        assert server.posts == []
    assert len(delayed) == 1 and len(samples) == 15
    fixed = [row for row in samples if row[0] == "complete" and row[1] is not None]
    assert len(fixed) == 4 and fixed[0][3] > fixed[0][2]
    assert [(row[4], row[5]) for row in fixed] == [(0, 1), (1, 2), (2, 3), (3, 4)]
    assert all(row[3] >= row[2] for row in fixed)
    assert all(
        row[2] == row[3] and row[4] == row[5]
        for row in samples
        if row[0] != "complete" or row[1] is None
    )
