"""Actual configured API -> leased one-request steps -> existing v2 publication."""

from pathlib import Path
from typing import Any

import pytest
from app.api import customer_acquisitions as api
from app.commerce import acquisition_runtime as runtime
from app.commerce.acquisition_models import CommerceAcquisitionCheckpoint as Checkpoint
from app.commerce.acquisition_models import CommerceAcquisitionJob as Job
from app.commerce.acquisition_models import CommerceAcquisitionSeen as Seen
from app.commerce.publication_contracts import IndependentManifest
from app.customers.access import CSRF_COOKIE
from app.jobs import commerce_acquisition_worker as runner
from app.settings import Settings
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_acquisition_checkpoint_contracts import profile
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import ORIGIN, FakeProvider
from tests.test_independent_publications import (
    configuration as configuration,
)
from tests.test_independent_publications import (
    customer_engine as customer_engine,
)
from tests.test_independent_publications import (
    ready,
    transport_for,
)
from tests.test_independent_publications import (
    replicas as replicas,
)


def configured(
    customer_engine: Engine,
    configuration: Settings,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Any:
    owned, request, _, _, body, token = ready(customer_engine, configuration, replicas)
    limits = profile()
    path = tmp_path / "profile.json"
    path.write_text(limits.model_dump_json())
    configuration.customer_independent_acquisition_enabled = True
    configuration.independent_acquisition_environment = "contract_test"
    configuration.independent_acquisition_profile_path = str(path)
    monkeypatch.setattr(api, "settings", configuration)
    monkeypatch.setattr(runtime, "utcnow", lambda: NOW)
    fixture, transport = transport_for(request)
    monkeypatch.setattr(runtime, "acquisition_transport", lambda _configuration: transport)
    client, _, provider = replicas
    client.app.include_router(api.router)  # type: ignore[attr-defined]
    path_prefix = f"/api/customer/v1/workspaces/{request.scope.workspace_id}/commerce/acquisitions"
    headers = {"Origin": ORIGIN, "X-CSRF-Token": client.cookies[CSRF_COOKIE]}
    intent = dict(
        goal_id=body.goal_id,
        expected_goal_revision=1,
        start=request.start.isoformat(),
        end=request.end.isoformat(),
    )
    return owned, request, fixture, client, provider, path_prefix, headers, intent


def test_configured_enqueue_runner_publication(
    customer_engine: Engine,
    configuration: Settings,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    owned, request, fixture, client, provider, prefix, headers, intent = configured(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    response = client.post(prefix, json=intent, headers=headers)
    assert response.status_code == 200, response.text
    identifier = response.json()["job_id"]
    replay = client.post(prefix, json=intent, headers=headers)
    assert replay.status_code == 200 and replay.json()["job_id"] == identifier
    assert fixture.seen == []
    runner.tick(customer_engine, configuration, lambda: provider)
    response = client.get(prefix + "/" + identifier)
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "completed", response.text
    document = owned.load(request.scope.workspace_id, response.json()["publication_id"])
    assert isinstance(document, IndependentManifest)
    assert document.acquisition.days[0].value_micros == -10_000_000
    assert document.correction_status == "unresolved" and document.maturity == "unqualified"
    assert len(fixture.seen) == 5
    with Session(customer_engine) as db:
        job = db.get(Job, identifier)
        assert job is not None and job.request_attempts == job.requests_completed == 5
        assert job.response_bytes == job.charged_bytes > 0
        assert db.scalar(select(func.count()).select_from(Checkpoint)) == 0
        assert db.scalar(select(func.count()).select_from(Seen)) == 0
    runner.tick(customer_engine, configuration, lambda: provider)
    assert len(fixture.seen) == 5


@pytest.mark.parametrize("change", ["session", "generation", "goal", "cancel"])
def test_real_mid_http_change_denies_publication(
    customer_engine: Engine,
    configuration: Settings,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    change: str,
) -> None:
    from app.commerce.models import CommerceEvidenceState, CommerceMeasurementPublication
    from app.customers.models import CustomerSession
    from app.goals.models import Goal

    owned, request, fixture, client, provider, prefix, headers, intent = configured(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    response = client.post(prefix, json=intent, headers=headers)
    assert response.status_code == 200, response.text
    identifier = response.json()["job_id"]
    with Session(customer_engine) as db:
        prior = db.scalar(select(func.count()).select_from(CommerceMeasurementPublication))

    def mutate(query: str) -> None:
        if "InletAgreements" not in query:
            return
        if change == "cancel":
            assert (
                client.post(prefix + "/" + identifier + "/cancel", headers=headers).status_code
                == 200
            )
            return
        with Session(customer_engine) as db:
            job = db.get(Job, identifier)
            assert job is not None
            if change == "session":
                session = db.get(CustomerSession, job.session_digest)
                assert session is not None
                session.revoked_at = 1
            elif change == "generation":
                evidence = db.get(CommerceEvidenceState, request.scope.store_id)
                assert evidence is not None
                evidence.generation += 1
            else:
                goal = db.get(Goal, request.scope.goal_id)
                assert goal is not None
                goal.revision += 1
            db.commit()

    fixture.after = mutate
    runner.tick(customer_engine, configuration, lambda: provider)
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(CommerceMeasurementPublication)) == prior
        assert db.scalar(select(func.count()).select_from(Checkpoint)) == 0
        assert db.scalar(select(func.count()).select_from(Seen)) == 0
        job = db.get(Job, identifier)
        if change == "cancel":
            assert job is not None and job.state == "cancelled"
        else:
            assert job is None


def test_one_step_lease_resume_and_disabled_cleanup(
    customer_engine: Engine,
    configuration: Settings,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from datetime import timedelta

    from app.commerce.acquisition_worker import claim

    _, request, fixture, client, provider, prefix, headers, intent = configured(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    response = client.post(prefix, json=intent, headers=headers)
    identifier = response.json()["job_id"]
    held = claim(
        customer_engine,
        request.scope.workspace_id,
        identifier,
        provider,
        configuration,
        profile(),
        lambda: NOW,
    )
    assert held is not None
    runner.tick(customer_engine, configuration, lambda: provider)
    assert not fixture.seen  # Active lease is excluded before round selection.
    configuration.customer_independent_acquisition_enabled = False
    monkeypatch.setattr(runtime, "utcnow", lambda: NOW + timedelta(minutes=30))
    runner.tick(
        customer_engine, configuration, lambda: (_ for _ in ()).throw(AssertionError("identity"))
    )
    with Session(customer_engine) as db:
        job = db.get(Job, identifier)
        assert job is not None and job.state == "expired"
        assert job.request_attempts == 1 and job.requests_completed == 0
        assert db.scalar(select(func.count()).select_from(Checkpoint)) == 0
    assert not fixture.seen


def test_real_transport_scenario_denied_before_constructor(
    monkeypatch: pytest.MonkeyPatch, configuration: Settings
) -> None:
    import httpx
    from app.commerce.independent_contracts import ScanUnavailable

    configuration.independent_acquisition_environment = "contract_test"
    monkeypatch.setattr(
        httpx, "HTTPTransport", lambda **_: (_ for _ in ()).throw(AssertionError("IO"))
    )
    with pytest.raises(ScanUnavailable, match="acquisition_test_transport_required"):
        runtime.acquisition_transport(configuration)


def test_retry_preserves_original_id_deadline_and_actual_byte_counts(
    customer_engine: Engine,
    configuration: Settings,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from datetime import timedelta

    import httpx

    _, _, fixture, client, provider, prefix, headers, intent = configured(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    response = client.post(prefix, json=intent, headers=headers)
    identifier = response.json()["job_id"]
    original_transport = runtime.acquisition_transport(configuration)
    monkeypatch.setattr(
        runtime,
        "acquisition_transport",
        lambda _: httpx.MockTransport(
            lambda request: (_ for _ in ()).throw(httpx.ConnectError("offline", request=request))
        ),
    )
    runner.tick(customer_engine, configuration, lambda: provider)
    with Session(customer_engine) as db:
        job = db.get(Job, identifier)
        assert job is not None and job.state == "running" and job.requests_completed == 0
        start, deadline = job.started_at, job.deadline_at
        assert job.error_code == "acquisition_transport_unavailable"
    monkeypatch.setattr(runtime, "acquisition_transport", lambda _: original_transport)
    runner.tick(customer_engine, configuration, lambda: provider)
    assert fixture.seen == []
    monkeypatch.setattr(runtime, "utcnow", lambda: NOW + timedelta(seconds=31))
    runner.tick(customer_engine, configuration, lambda: provider)
    with Session(customer_engine) as db:
        job = db.get(Job, identifier)
        assert job is not None and job.state == "completed"
        assert (job.started_at, job.deadline_at) == (start, deadline)
        assert job.request_attempts == 6 and job.requests_completed == 5
        assert job.charged_bytes > job.response_bytes > 0


def test_factory_failure_cannot_starve_next_workspace_with_one_slot(
    customer_engine: Engine,
    configuration: Settings,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import httpx

    values = configured(customer_engine, configuration, replicas, monkeypatch, tmp_path)
    _, _, fixture, client, provider, prefix, headers, intent = values
    limits = profile(tick_request_budget=1, tick_workspace_budget=1)
    Path(configuration.independent_acquisition_profile_path or "").write_text(
        limits.model_dump_json()
    )
    first = client.post(prefix, json=intent, headers=headers)
    assert first.status_code == 200, first.text
    from tests.test_commerce_publications import complete

    monkeypatch.setattr(
        "tests.test_descriptive_comparisons.complete",
        lambda db, config: complete(db, config, slug="second"),
    )
    client.cookies.clear()
    from tests.test_customer_identity import login

    monkeypatch.setattr(
        "tests.test_independent_publications.login",
        lambda other, token: login(other, "second-" + token),
    )
    _, _, _, client, _, prefix, headers, intent = configured(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    Path(configuration.independent_acquisition_profile_path or "").write_text(
        limits.model_dump_json()
    )
    second = client.post(prefix, json=intent, headers=headers)
    assert second.status_code == 200, second.text
    identifiers = {first.json()["job_id"], second.json()["job_id"]}

    def unavailable(_: Settings) -> httpx.BaseTransport:
        raise RuntimeError("offline transport factory")

    monkeypatch.setattr(runtime, "acquisition_transport", unavailable)
    runner.tick(customer_engine, configuration, lambda: provider)
    with Session(customer_engine) as db:
        first_served = db.scalar(select(Job).where(Job.request_attempts == 1))
        assert first_served is not None
        deferred = first_served.id
    runner.tick(customer_engine, configuration, lambda: provider)
    with Session(customer_engine) as db:
        jobs = list(db.scalars(select(Job)))
        assert {j.id for j in jobs} == identifiers
        assert all(j.request_attempts == 1 for j in jobs)
        assert all(j.error_code == "acquisition_transport_unavailable" for j in jobs)
        assert deferred in identifiers
    assert fixture.seen == []


def test_disabled_or_sqlite_integrity_off_cannot_enqueue(
    customer_engine: Engine,
    configuration: Settings,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from sqlalchemy import text

    _, _, fixture, client, _, prefix, headers, intent = configured(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    configuration.customer_independent_acquisition_enabled = False
    response = client.post(prefix, json=intent, headers=headers)
    assert response.status_code == 409
    if customer_engine.dialect.name == "sqlite":
        configuration.customer_independent_acquisition_enabled = True
        with customer_engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        response = client.post(prefix, json=intent, headers=headers)
        assert (
            response.status_code == 409
            and response.json()["detail"] == "acquisition_storage_unavailable"
        )
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(Job)) == 0
        if customer_engine.dialect.name == "sqlite":
            db.execute(text("PRAGMA foreign_keys=ON"))
    assert not fixture.seen


def test_same_owner_new_session_does_not_adopt_existing_acquisition(
    customer_engine: Engine,
    configuration: Settings,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from tests.test_customer_identity import login

    _, _, fixture, client, _, prefix, headers, intent = configured(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    response = client.post(prefix, json=intent, headers=headers)
    assert response.status_code == 200, response.text
    identifier = response.json()["job_id"]
    client.cookies.clear()
    login(client, "independent-publication-owner:second-session")
    headers["X-CSRF-Token"] = client.cookies[CSRF_COOKIE]
    assert client.get(prefix + "/" + identifier).status_code == 404
    response = client.post(prefix, json=intent, headers=headers)
    assert (
        response.status_code == 409 and response.json()["detail"] == "acquisition_active_conflict"
    )
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(Job)) == 1
    assert not fixture.seen


def test_abandoned_read_lease_resumes_same_acquisition_after_expiry(
    customer_engine: Engine,
    configuration: Settings,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from datetime import timedelta

    from app.commerce.acquisition_worker import claim

    _, request, fixture, client, provider, prefix, headers, intent = configured(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    response = client.post(prefix, json=intent, headers=headers)
    identifier = response.json()["job_id"]
    abandoned = claim(
        customer_engine,
        request.scope.workspace_id,
        identifier,
        provider,
        configuration,
        profile(),
        lambda: NOW,
    )
    assert abandoned is not None
    monkeypatch.setattr(runtime, "utcnow", lambda: NOW + timedelta(seconds=16))
    runner.tick(customer_engine, configuration, lambda: provider)
    with Session(customer_engine) as db:
        job = db.get(Job, identifier)
        assert job is not None and job.state == "completed"
        assert job.request_attempts == 6 and job.requests_completed == 5
        from app.shopify.security import utc

        assert job.started_at is not None
        assert utc(job.started_at) == abandoned.started_at
        assert utc(job.deadline_at) == abandoned.deadline_at
        assert job.charged_bytes > job.response_bytes
    assert len(fixture.seen) == 5
