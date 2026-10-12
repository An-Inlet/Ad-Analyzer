"""Assembled mock HTTP evidence, exact schema admission and durable authority fences."""

import copy
import io
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.api.customer_exports import router as export_router
from app.lifecycle.privacy import bump_workspace_export_revision, workspace_export_revision
from app.main import app
from app.planning_documents import authority, repository
from app.planning_documents import google_budget_http_service as http_service
from app.planning_documents.google_budget_events import GoogleBudgetObservationV1
from app.planning_documents.google_budget_http_events import GoogleBudgetHTTPObservationV1
from app.planning_documents.google_budget_http_fixture import GoogleBudgetHTTPFixture
from app.planning_documents.google_budget_observation_service import GoogleBudgetObservationService
from app.planning_documents.models import PlanEventRow, PlanRequestRow
from app.planning_documents.storage import canonical, document_for_row
from app.publication import customer_intents
from app.settings import Settings, settings
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.creative_q07_fixture import planning_snapshot
from tests.google_budget_runtime_fixture import install_http_fixture
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_exports import unpack
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_google_budget_observation_service import customer_engine as customer_engine
from tests.test_google_budget_observation_service import principal
from tests.test_owner_review_runtime_api import generation
from tests.test_owner_runtime_composition import actual_owner as actual_owner
from tests.test_shopify_sales import configuration as configuration


def setup(actual: Any, engine: Engine, patch: pytest.MonkeyPatch) -> Any:
    f, create_body, calls, catalog, alice, root = actual
    created = alice.post(root, headers=headers(alice), json=create_body)
    assert created.status_code == 201, created.text
    url = root + "/" + created.json()["plan_id"]
    generated = alice.post(url + "/generate", headers=headers(alice), json=generation())
    assert generated.status_code == 200, generated.text
    result = generated.json()
    action = result["document"]["google_budget_owner_review"]["reviews"][0]["action_key"]
    body = dict(
        expected_version=1,
        expected_event_sequence=0,
        document_digest=result["document_digest"],
        action_key=action,
        action_digest=result["action_digests"][action],
        request_key="http-admission-request",
    )
    bundle = install_http_fixture(
        engine,
        patch,
        f.basis.workspace_id,
        f.basis.account_id,
        catalog["native_observation"]["time_zone"],
    )
    return f, calls, alice, root, url, body, bundle


def test_http_durable_mixed_history_recovery_archive_and_erasure(
    actual_owner: Any,
    customer_engine: Engine,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    f, calls, alice, root, url, body, bundle = setup(actual_owner, customer_engine, monkeypatch)
    owner = principal(customer_engine, alice)
    effects, reads = financial_counts(customer_engine), list(calls)
    legacy = alice.post(url + "/budget-observations", headers=headers(alice), json=body)
    assert legacy.status_code == 200, legacy.text
    with Session(customer_engine) as db:
        row = db.get(PlanEventRow, (f.basis.workspace_id, url.rsplit("/", 1)[1], 1))
        assert row is not None
        old_values = repository.values(row)
    body = {**body, "expected_event_sequence": 1}  # same key is distinct by explicit operation
    endpoint = url + "/budget-http-observations"
    capability = alice.get(root + "/capabilities").json()
    assert capability["google_budget_observation"] == "mock_http"
    assert alice.post(endpoint, json=body).status_code == 403
    for field in ("api_version", "provenance", "proof", "profile_digest", "account_id"):
        assert (
            alice.post(endpoint, headers=headers(alice), json={**body, field: "bad"}).status_code
            == 422
        )
    with monkeypatch.context() as patch:
        patch.setattr(settings, "customer_google_budget_http_mode", "disabled")
        assert alice.post(endpoint, headers=headers(alice), json=body).status_code == 503
    observed = alice.post(endpoint, headers=headers(alice), json=body)
    assert observed.status_code == 200, observed.text
    value = observed.json()
    event = GoogleBudgetHTTPObservationV1.model_validate(value["event"])
    assert value["event_sequence"] == 2 and event.provenance == "mock_http"
    assert event.provider_authentication == "not_verified"
    assert event.proof.ticket.api_version == "v24" and event.implementation == "not_assessed"
    assert "inlet-synthetic-mock-only" not in observed.text
    saved = planning_snapshot(customer_engine)
    with monkeypatch.context() as patch:

        def no_acquire(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("replay must not reacquire")

        patch.setattr(GoogleBudgetHTTPFixture, "acquire", no_acquire)
        assert alice.post(endpoint, headers=headers(alice), json=body).json() == value
        assert (
            alice.post(
                endpoint, headers=headers(alice), json={**body, "expected_event_sequence": 2}
            ).status_code
            == 409
        )
    monkeypatch.setattr(settings, "customer_google_budget_http_mode", "disabled")
    assert alice.post(endpoint, headers=headers(alice), json=body).status_code == 503
    receipt = root + "/requests/budget_http_observe/" + body["request_key"]
    recovered = alice.get(receipt)
    assert recovered.status_code == 200 and recovered.json() == value
    assert recovered.headers["cache-control"] == "no-store"
    assert (
        alice.get(root + "/requests/budget_observe/" + body["request_key"]).json() == legacy.json()
    )
    page1 = alice.get(url + "/events?limit=1").json()
    page2 = alice.get(url + "/events?limit=1&cursor=" + page1["next_cursor"]).json()
    assert page1["items"] == [legacy.json()] and page2["items"] == [value]
    assert page2["next_cursor"] is None
    assert (
        alice.get(
            receipt.replace(f"/workspaces/{f.basis.workspace_id}/", "/workspaces/999999/")
        ).status_code
        == 404
    )
    assert replicas[1].get(receipt).status_code in (401, 403, 404)
    with Session(customer_engine) as db:
        row = db.get(PlanEventRow, (f.basis.workspace_id, event.plan_id, 1))
        assert row is not None and repository.values(row) == old_values
        new = db.get(PlanEventRow, (f.basis.workspace_id, event.plan_id, 2))
        assert new is not None
        assert new.canonical_json == canonical(event) and new.digest == event.digest()
        assert document_for_row(PlanEventRow.__tablename__, repository.values(new)) == event
    for damage in (
        "event-origin",
        "proof-origin",
        "ticket-origin",
        "api-version",
        "event-schema",
        "proof-schema",
        "authentication",
        "source",
        "actor",
    ):
        forged = copy.deepcopy(value["event"])
        if damage == "event-origin":
            forged["provenance"] = "injected_fixture"
        elif damage == "proof-origin":
            forged["proof"]["provenance"] = "injected_fixture"
        elif damage == "ticket-origin":
            forged["proof"]["ticket"]["provenance"] = "injected_fixture"
        elif damage == "api-version":
            forged["proof"]["ticket"]["api_version"] = "v22"
        elif damage == "event-schema":
            forged["schema_version"] = "inlet.google-budget-observation.v1"
        elif damage == "proof-schema":
            forged["proof"]["schema_version"] = "inlet.google-budget-read-proof.v1"
        elif damage == "authentication":
            forged["provider_authentication"] = "verified"
        elif damage == "source":
            forged["proof"]["ticket"]["source_binding_digest"] = "0" * 64
        else:
            forged["advertising_writes_enabled"] = True
        with pytest.raises(ValidationError):
            GoogleBudgetHTTPObservationV1.model_validate(forged)
    with pytest.raises(ValidationError):
        GoogleBudgetObservationV1.model_validate(value["event"])
    with pytest.raises(ValidationError):
        GoogleBudgetHTTPObservationV1.model_validate(legacy.json()["event"])
    monkeypatch.setattr(settings, "customer_export_enabled", True)
    monkeypatch.setattr(settings, "media_storage_mode", "local_dev")
    monkeypatch.setattr(settings, "media_local_directory", str(tmp_path / "media"))
    alice.app.include_router(export_router)
    exports = f"/api/customer/v1/workspaces/{f.basis.workspace_id}/exports"
    exported = alice.post(
        exports, headers={**headers(alice), "Idempotency-Key": "http-history-export"}, json={}
    )
    assert exported.status_code == 200, exported.text
    download_url = exports + "/" + exported.json()["request_id"] + "/download"
    download = alice.get(download_url)
    assert download.status_code == 200, download.text[:500]
    original_manifest, entries = unpack(io.BytesIO(download.content))
    (tmp_path / "http-original-archive.tar").write_bytes(download.content)
    archived = [
        json.loads(line)["document"]
        for line in entries["data/planning_document_events.jsonl"].splitlines()
    ]
    assert archived == [legacy.json()["event"], value["event"]]
    assert planning_snapshot(customer_engine) == saved
    replicas[2].revoked.add(owner.user.subject)
    for path in (receipt, url + "/events", download_url):
        assert alice.get(path).status_code == 401
    replicas[2].revoked.clear()
    with Session(customer_engine) as db, db.begin():
        bump_workspace_export_revision(db, f.basis.workspace_id)
        erased_revision = workspace_export_revision(db, f.basis.workspace_id)
    assert alice.get(receipt).status_code == 404
    assert alice.get(url + "/events").status_code == 404
    rebuilt = alice.get(download_url)
    assert rebuilt.status_code == 200, rebuilt.text[:500]
    rebuilt_manifest, rebuilt_entries = unpack(io.BytesIO(rebuilt.content))
    assert rebuilt_manifest["snapshot_revision"] == original_manifest["snapshot_revision"] + 1
    assert erased_revision > original_manifest["privacy_fence"]["workspace_revision"]
    assert rebuilt_manifest["privacy_fence"]["workspace_revision"] == erased_revision
    assert rebuilt_entries["data/planning_document_events.jsonl"] == b""
    for previous in (legacy.json()["event"]["event_id"], event.event_id):
        assert all(previous.encode() not in payload for payload in rebuilt_entries.values())
    assert (
        alice.get(exports + "/" + exported.json()["request_id"]).json()["retained_artifact"]
        is False
    )
    (tmp_path / "http-rebuilt-archive.tar").write_bytes(rebuilt.content)
    assert all(not rows for rows in planning_snapshot(customer_engine))
    assert calls == reads and financial_counts(customer_engine) == effects == (0,) * 6
    (tmp_path / "http-admission-history.json").write_text(
        json.dumps(
            dict(
                legacy=legacy.json(),
                observed=value,
                archive=archived,
                erased=True,
            )
        )
    )


def test_http_late_authority_configuration_and_atomic_rollback(
    actual_owner: Any,
    customer_engine: Engine,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    f, calls, alice, _, url, body, bundle = setup(actual_owner, customer_engine, monkeypatch)
    owner = principal(customer_engine, alice)
    endpoint = url + "/budget-http-observations"
    before = planning_snapshot(customer_engine)
    effects, reads = financial_counts(customer_engine), list(calls)
    original_handle = httpx.MockTransport.handle_request
    for damage in ("io-disable", "io-revoke"):
        reads_seen: list[bool] = []
        with monkeypatch.context() as patch:

            def during_io(
                self: Any,
                request: Any,
                damage: str = damage,
                reads_seen: list[bool] = reads_seen,
            ) -> Any:
                response = original_handle(self, request)
                reads_seen.append(True)
                if damage == "io-disable":
                    patch.setattr(settings, "customer_google_budget_http_mode", "disabled")
                else:
                    replicas[2].revoked.add(owner.user.subject)
                return response

            patch.setattr(httpx.MockTransport, "handle_request", during_io)
            response = alice.post(endpoint, headers=headers(alice), json=body)
            assert response.status_code == 503, response.text
        replicas[2].revoked.clear()
        assert reads_seen == [True]
        assert planning_snapshot(customer_engine) == before
    original = GoogleBudgetHTTPFixture.acquire
    for damage in ("disable", "replace", "revoke", "source", "privacy", "deadline"):
        with monkeypatch.context() as patch:

            def acquired(
                self: Any, ticket: Any, check: Any, clock: Any, guard: Any, damage: str = damage
            ) -> Any:
                result = original(self, ticket, check, clock, guard)
                if damage == "disable":
                    patch.setattr(settings, "customer_google_budget_http_mode", "disabled")
                elif damage == "replace":
                    patch.setattr(
                        app.state,
                        "google_budget_http_fixture",
                        GoogleBudgetHTTPFixture.model_validate(bundle.model_dump()),
                    )
                elif damage == "revoke":
                    replicas[2].revoked.add(owner.user.subject)
                elif damage == "source":
                    from app.planning_documents import google_budget_http_service as module

                    real = customer_intents.account
                    patch.setattr(
                        customer_intents,
                        "account",
                        lambda *a, **k: real(*a, **k).model_copy(
                            update={"connection_version": "changed"}
                        ),
                    )
                elif damage == "privacy":
                    from app.planning_documents import google_budget_http_service as module

                    patch.setattr(
                        module, "workspace_export_revision", lambda *a: ticket.privacy_revision + 1
                    )
                else:
                    from app.planning_documents import google_budget_http_service as module

                    patch.setattr(module, "database_utc_now", lambda *a: ticket.expires_at)
                return result

            patch.setattr(GoogleBudgetHTTPFixture, "acquire", acquired)
            result = alice.post(endpoint, headers=headers(alice), json=body)
            assert result.status_code == (
                401 if damage == "revoke" else 503 if damage in ("disable", "replace") else 409
            ), result.text
        replicas[2].revoked.clear()
        assert planning_snapshot(customer_engine) == before
    append = GoogleBudgetObservationService._append
    for damage in ("disable", "deadline", "authority"):
        inserted: list[bool] = []
        with monkeypatch.context() as patch:

            def changed_after_inserts(
                *args: Any, damage: str = damage, inserted: list[bool] = inserted, **kwargs: Any
            ) -> Any:
                result = append(*args, **kwargs)
                db, _, req, event = args[:4]
                assert db.get(PlanEventRow, (req.workspace_id, req.plan_id, 1)) is not None
                receipt = db.scalar(
                    select(PlanRequestRow).where(
                        PlanRequestRow.operation == "budget_http_observe",
                        PlanRequestRow.request_key == req.request_key,
                    )
                )
                assert receipt is not None
                inserted.append(True)
                if damage == "disable":
                    patch.setattr(settings, "customer_google_budget_http_mode", "disabled")
                elif damage == "deadline":
                    patch.setattr(
                        http_service, "database_utc_now", lambda *a: event.proof.ticket.expires_at
                    )
                else:

                    def refuse(*args: Any) -> None:
                        raise HTTPException(409, "original authority unavailable")

                    patch.setattr(authority, "final", refuse)
                return result

            patch.setattr(
                GoogleBudgetObservationService, "_append", staticmethod(changed_after_inserts)
            )
            result = alice.post(endpoint, headers=headers(alice), json=body)
            assert result.status_code == (503 if damage == "disable" else 409), result.text
        assert inserted == [True]
        assert planning_snapshot(customer_engine) == before
    conflict = alice.post(
        endpoint, headers=headers(alice), json={**body, "expected_event_sequence": 1}
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["detail"] == "HTTP observation source, plan, privacy or deadline changed"
    assert planning_snapshot(customer_engine) == before
    assert calls == reads and financial_counts(customer_engine) == effects


def test_assembled_http_observation_browser(
    customer_engine: Engine,
    request: pytest.FixtureRequest,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from tests import test_owner_review_planning_browser as browser
    from tests.test_owner_runtime_composition import owner_config

    owner_config(monkeypatch, tmp_path / "media")
    browser.test_actual_owner_review_planning_browser(
        customer_engine,
        request,
        configuration,
        replicas,
        monkeypatch,
        tmp_path,
        "budget_http",
        configured_runtime=True,
    )
