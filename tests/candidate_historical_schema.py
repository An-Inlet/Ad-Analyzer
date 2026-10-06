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
    without_google_capture(monkeypatch, engine)

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
    without_session_automation(monkeypatch, engine)
    from app.optimization_candidates import review_guard

    def check(*args: object, **kwargs: object) -> None:
        pass

    monkeypatch.setattr(review_guard, "check", check)


def without_session_automation(monkeypatch: pytest.MonkeyPatch, engine: Engine) -> None:
    """Pre0072 fixtures have only the exact-human variant; never an automatic admission.

    Use the former authority discriminator while exercising the real existing
    approval/accounting checks. No application missing-table fallback is installed.
    Current0072 tests always use the real discriminator and mandatory guard.
    """
    assert "provider_automatic_decisions" not in inspect(engine).get_table_names()
    from app.session_automation import authority
    from app.session_automation.contracts import CustomerExactApprovalAuthority

    monkeypatch.setattr(authority, "automatic", lambda row: False)
    monkeypatch.setattr(authority, "for_run", lambda row: CustomerExactApprovalAuthority())


def without_google_capture(monkeypatch: pytest.MonkeyPatch, engine: Engine) -> None:
    """Pre0066 acknowledged fixtures have no durable original Google capture table.

    Keep actual transport/normalized response/receipt/replacement behavior while
    omitting only the later capture append. Current-head capture tests stay real.
    """
    assert "google_original_completions" not in inspect(engine).get_table_names()
    from app.publication import google_completion

    def capture(*args: object, **kwargs: object) -> None:
        pass

    monkeypatch.setattr(google_completion, "capture_response", capture)
