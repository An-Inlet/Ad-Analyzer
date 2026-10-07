"""A real prior native budget attempt consumes bootstrap across periods and policies."""

from pathlib import Path

import pytest
from app.initial_planning.automatic_source import no_prior_budget
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.reported_rule_fixture import ready_reported_rule
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_shopify_sales import configuration as configuration


def test_actual_prior_budget_cannot_be_reinterpreted_as_first_action(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with Session(customer_engine) as db:
        _, _, work, _, _, _, _ = ready_reported_rule(db, configuration, tmp_path, monkeypatch)
        with pytest.raises(HTTPException, match="initial_rule_current_evidence_unavailable"):
            no_prior_budget(db, work.scope)
        # Changing only a future period/policy reference does not erase protected
        # native budget history. This is not presented as a valid execution mandate.
        future_scope = work.scope.model_copy(
            update={
                "mandate": work.scope.mandate.model_copy(
                    update={"ledger_id": "a" * 32, "revision": work.scope.mandate.revision + 1},
                )
            }
        )
        with pytest.raises(HTTPException, match="initial_rule_current_evidence_unavailable"):
            no_prior_budget(db, future_scope)
