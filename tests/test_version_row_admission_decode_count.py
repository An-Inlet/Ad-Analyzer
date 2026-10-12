"""Named decoder counts on real retained evidence; no timing or API acceptance claim.

This regression deliberately imports no new admission implementation. On the old
source the expected optimized history count fails (one actual repeated decoder).
The fixture acquires actual source/input evidence, then composes/stores directly;
real generation acceptance remains the separate report/retraction API journey.
"""

from pathlib import Path
from typing import Any, cast

import pytest
from app.planning_documents import repository
from app.planning_documents import selected_plan_history as history
from app.planning_documents.models import PlanRow
from app.planning_documents.storage import canonical
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.owner_review_retained_fixture import stored
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def test_each_version_invocation_decodes_original_row_once(
    customer_engine: Engine,
    configuration: Any,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    document, _, _, calls = stored(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    expected_json = document.model_dump_json()
    expected_digest = document.digest()
    expected_canonical = canonical(document)
    provider_calls = list(calls)
    original_repository = cast(Any, repository).document_for_row
    original_history = cast(Any, history).document_for_row
    decoded: list[str] = []

    def repository_decode(*args: Any, **kwargs: Any) -> Any:
        decoded.append("repository")
        return original_repository(*args, **kwargs)

    def history_decode(*args: Any, **kwargs: Any) -> Any:
        decoded.append("history")
        return original_history(*args, **kwargs)

    monkeypatch.setattr(repository, "document_for_row", repository_decode)
    monkeypatch.setattr(history, "document_for_row", history_decode)
    with Session(customer_engine) as db, db.begin():
        plan = db.get(PlanRow, (document.inputs.workspace_id, document.inputs.plan_id))
        assert plan is not None
        # Each invocation must admit its own first row, never reuse across calls.
        for _ in range(2):
            start = len(decoded)
            row, actual = repository.version(db, plan)
            assert actual.model_dump_json() == expected_json
            assert actual.digest() == expected_digest
            assert row.canonical_json == expected_canonical
            assert decoded[start:] == ["repository"]
    assert calls == provider_calls
