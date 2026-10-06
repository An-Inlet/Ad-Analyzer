"""Explicit pre-0062 migration fixtures; never used by application runtime.

These tests intentionally invoke current producer helpers against historical schemas.
No candidate can exist before0062; stub only its newly introduced erasure hooks.
"""

import pytest
from app.optimization_candidates import invalidation
from sqlalchemy import Engine, inspect
from sqlalchemy.orm import Session


def without_candidates(monkeypatch: pytest.MonkeyPatch, engine: Engine) -> None:
    assert "optimization_candidate_jobs" not in inspect(engine).get_table_names()
    without_candidate_reviews(monkeypatch, engine)

    def workspace(db: Session, wid: int) -> None:
        pass

    def scoped(db: Session, wid: int, identifier: str) -> None:
        pass

    monkeypatch.setattr(invalidation, "erase_workspace_candidates", workspace)
    monkeypatch.setattr(invalidation, "erase_source_candidates", scoped)
    monkeypatch.setattr(invalidation, "erase_attempt_candidates", scoped)


def without_candidate_reviews(monkeypatch: pytest.MonkeyPatch, engine: Engine) -> None:
    """Pre0068 fixtures cannot contain marked reviews; stub only new forward guard."""
    assert "optimization_candidate_reviews" not in inspect(engine).get_table_names()
    from app.optimization_candidates import review_guard

    def check(*args: object, **kwargs: object) -> None:
        pass

    monkeypatch.setattr(review_guard, "check", check)
