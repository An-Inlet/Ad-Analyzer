from pathlib import Path
from typing import Any

import pytest
from app.customers.models import CustomerSession
from app.settings import Settings
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_commerce_acquisition_jobs import configured
from tests.test_customer_identity import FakeProvider
from tests.test_independent_publications import (
    configuration as configuration,
)
from tests.test_independent_publications import (
    customer_engine as customer_engine,
)
from tests.test_independent_publications import (
    replicas as replicas,
)


def test_recovery_cancel_disabled_runtime_and_foreign_goal(
    customer_engine: Engine,
    configuration: Settings,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _, _, _, client, _, prefix, headers, intent = configured(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    url = prefix + "?goal_id=" + intent["goal_id"]
    assert client.get(url).json()["items"] == []
    row = client.post(prefix, json=intent, headers=headers).json()
    recovered = client.get(url)
    assert recovered.status_code == 200, recovered.text
    assert recovered.headers["cache-control"] == "no-store"
    item = recovered.json()["items"][0]
    assert item["status"]["job_id"] == row["job_id"]
    assert item["start"] == intent["start"] and item["goal_revision"] == 1
    assert recovered.json()["truncated"] is False
    conflicting = {**intent, "end": "2026-10-03"}
    assert client.post(prefix, json=conflicting, headers=headers).status_code == 409
    assert len(client.get(url).json()["items"]) == 1
    configuration.customer_independent_acquisition_enabled = False
    assert client.get(url).status_code == 200
    cancelled = client.post(prefix + "/" + row["job_id"] + "/cancel", headers=headers)
    assert cancelled.status_code == 200 and cancelled.json()["state"] == "cancelled"
    assert client.get(url).json()["items"][0]["status"]["state"] == "cancelled"
    assert client.get(prefix + "?goal_id=" + "f" * 32).status_code == 404
    assert client.get(prefix + "?goal_id=invalid").status_code == 422
    with Session(customer_engine) as db:
        session = db.scalar(select(CustomerSession).where(CustomerSession.revoked_at.is_(None)))
        assert session is not None
        from tests.test_commerce_measurement import NOW

        session.revoked_at = int(NOW.timestamp())
        db.commit()
    assert client.get(url).status_code in {401, 403}


def test_recovery_bounded_original_session_only(
    customer_engine: Engine,
    configuration: Settings,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _, _, _, client, _, prefix, headers, intent = configured(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    # Every job is created through the ordinary owned API, not inserted as a fixture.
    ids = []
    for _ in range(21):
        row = client.post(prefix, json=intent, headers=headers)
        assert row.status_code == 200, row.text
        ids.append(row.json()["job_id"])
        assert client.post(prefix + "/" + ids[-1] + "/cancel", headers=headers).status_code == 200
    result = client.get(prefix + "?goal_id=" + intent["goal_id"]).json()
    assert result["truncated"] and len(result["items"]) == 20
    assert len({row["status"]["job_id"] for row in result["items"]}) == 20
    from tests.test_customer_identity import login

    client.cookies.clear()
    login(client, "independent-publication-owner:2")
    fresh: Any = client.get(prefix + "?goal_id=" + intent["goal_id"])
    assert fresh.status_code == 200 and fresh.json()["items"] == []


def test_different_original_session_cannot_adopt_active_read(
    customer_engine: Engine,
    configuration: Settings,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app.customers.access import CSRF_COOKIE

    from tests.test_customer_identity import ORIGIN, login

    _, _, _, client, _, prefix, headers, intent = configured(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    created = client.post(prefix, json=intent, headers=headers)
    assert created.status_code == 200, created.text
    identifier = created.json()["job_id"]
    client.cookies.clear()
    login(client, "independent-publication-owner:other-session")
    other_headers = {"Origin": ORIGIN, "X-CSRF-Token": client.cookies[CSRF_COOKIE]}
    recovered = client.get(prefix + "?goal_id=" + intent["goal_id"])
    assert recovered.status_code == 200 and recovered.json()["items"] == []
    assert client.get(prefix + "/" + identifier).status_code == 404
    assert (
        client.post(prefix + "/" + identifier + "/cancel", headers=other_headers).status_code == 404
    )
    conflict = client.post(prefix, json=intent, headers=other_headers)
    assert (
        conflict.status_code == 409 and conflict.json()["detail"] == "acquisition_active_conflict"
    )
