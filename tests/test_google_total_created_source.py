"""Actual original two-step source and current owned reconstruction, no envelope API yet."""

from pathlib import Path

import pytest
from sqlalchemy import Engine

from tests.google_created_retained_fixture import retained_google_created
from tests.test_customer_identity import customer_engine as customer_engine

pytestmark = pytest.mark.planning_boundary


def test_total_created_source(customer_engine: Engine, tmp_path: Path) -> None:
    with retained_google_created(customer_engine, tmp_path / "original", "total_created") as (
        _,
        ids,
    ):
        assert ids.provider_posts == 2
        assert [pin.step_id for pin in ids.attempts] == ["budget", "campaign"]
        assert (
            ids.attempts[0].resource_name and "/campaignBudgets/" in ids.attempts[0].resource_name
        )
        assert ids.attempts[1].resource_name and "/campaigns/" in ids.attempts[1].resource_name
