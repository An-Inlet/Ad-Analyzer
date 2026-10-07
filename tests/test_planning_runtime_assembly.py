from pathlib import Path
from typing import Any

import pytest
from app.initial_planning.models import PreviewRow
from app.initial_planning.preview_binding import bind_preview_row
from app.initial_planning.review_bridge import current_preview
from app.lifecycle.export_serializers import serialize
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.planning_runtime_fixture import configured_journey
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration


def test_actual_configured_api_worker_native_preview(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> None:
    with Session(customer_engine) as db:
        alice, provider, wid, principal, runtime, _, value, _, requests, profile = (
            configured_journey(db, customer_engine, configuration, tmp_path, monkeypatch, replicas)
        )
        assert runtime.initial.native is None and runtime.initial.profile == profile
        root = f"/api/customer/v1/workspaces/{wid}/initial-planning"
        response = alice.get(root + "/previews/" + value["id"])
        assert response.status_code == 200 and response.json() == value, response.text
        assert (
            alice.get(root + "/previews/" + value["id"] + "/review-status").json()[
                "request_available"
            ]
            is False
        )
        row = db.get(PreviewRow, value["id"])
        assert row is not None and row.native_state_digest is None
        assert "choice" not in row.intent and len(requests) >= 9
        assert (
            bind_preview_row({c.name: getattr(row, c.name) for c in row.__table__.columns}).digest()
            == row.document_digest
        )

        row_values = {c.name: getattr(row, c.name) for c in row.__table__.columns}
        exported, omitted = serialize("initial_plan_previews", row_values)
        assert exported["document"] == value
        assert "original_session_digest" not in exported
        with pytest.raises(HTTPException) as blocked:
            current_preview(db, principal, provider, wid, value["id"], runtime.initial)
        assert blocked.value.detail == "initial_preview_native_read_unqualified"


@pytest.mark.parametrize("change", ["session", "generation", "profile", "expiry"])
def test_configured_preview_denies_changed_authority(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    change: str,
) -> None:
    from datetime import timedelta

    from app.meta.models import MetaConnection
    from app.planning_reporting.contracts import PlanningReportingProfileV1
    from app.settings import settings

    with Session(customer_engine) as db:
        alice, provider, wid, principal, _, job, value, clock, requests, profile = (
            configured_journey(db, customer_engine, configuration, tmp_path, monkeypatch, replicas)
        )
        count = len(requests)
        if change == "session":
            provider.revoked.add(principal.user.subject)
        elif change == "generation":
            source = db.get(MetaConnection, job.source_connection_id)
            assert source is not None
            source.generation += 1
            db.commit()
        elif change == "profile":
            changed = PlanningReportingProfileV1.model_validate(
                {**profile.model_dump(), "revision": 2}
            )
            path = tmp_path / "changed-profile.json"
            path.write_text(changed.model_dump_json())
            monkeypatch.setattr(settings, "planning_reporting_profile_path", str(path))
            monkeypatch.setattr(settings, "planning_reporting_profile_digest", changed.digest())
        else:
            clock[0] += timedelta(seconds=301)
        result = alice.get(
            f"/api/customer/v1/workspaces/{wid}/initial-planning/previews/{value['id']}"
        )
        assert result.status_code in {401, 403, 409}, result.text
        assert len(requests) == count
