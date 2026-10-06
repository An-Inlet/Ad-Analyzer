"""Explicit historical fixture adapter, never a production missing-table fallback."""

import pytest
from app.outcome_feedback import invalidation
from sqlalchemy import Engine, inspect
from sqlalchemy.orm import Session


def without_feedback(monkeypatch: pytest.MonkeyPatch, engine: Engine) -> None:
    assert "outcome_assessments_v3" not in inspect(engine).get_table_names()

    def workspace(db: Session, wid: int) -> None:
        pass

    def scoped(db: Session, wid: int, identifier: str) -> None:
        pass

    monkeypatch.setattr(invalidation, "erase_workspace_feedback", workspace)
    monkeypatch.setattr(invalidation, "erase_source_feedback", scoped)
    monkeypatch.setattr(invalidation, "erase_attempt_feedback", scoped)
