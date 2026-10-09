"""Original-wire evidence and actual owned API delivery; no settlement authority."""

import json
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.customers.access import SESSION_COOKIE, digest
from app.customers.models import CustomerMembership, CustomerSession
from app.publication.execution_models import (
    GoogleOriginalCompletion,
    ProviderExecutionAttempt,
    ProviderExecutionResponse,
    ProviderExposureReservation,
)
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.google_runtime_fixture import configured_customer
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration


def first_attempt(
    engine: Engine,
    config: Settings,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    *,
    timeout: bool = False,
) -> Any:
    alice, base, body, draft, revision, server, requests, control = configured_customer(
        engine, config, path, monkeypatch, replicas
    )

    def post(route: str, data: Any = None, code: int = 200) -> Any:
        response = alice.post(base + route, json=data, headers=headers(alice))
        assert response.status_code == code, response.text
        return response.json()

    policy = post("/mandates", body, 201)
    post(
        f"/mandates/{policy['id']}/consent",
        {"expected_revision": policy["revision"], "policy_digest": policy["policy_digest"]},
    )
    catalog = post("/configuration-options", {"draft_id": draft})
    review = post(
        "/creation-reviews",
        {
            "draft_id": draft,
            "draft_revision": revision,
            "mandate_id": policy["id"],
            "mandate_revision": policy["revision"],
            "google": {
                "catalog_option_id": catalog["options"][0]["id"],
                "daily_budget_micros": 20,
                "max_cpc_micros": 1,
                "search_partners": False,
            },
        },
        201,
    )
    post(
        f"/reviews/{review['id']}/approval",
        {"review_digest": review["review_digest"], "plan_digest": review["plan_digest"]},
    )
    run = post(f"/reviews/{review['id']}/runs", code=201)
    server.timeout = timeout
    post(f"/runs/{run['id']}/advance")
    with Session(engine) as db:
        attempt = db.scalar(select(ProviderExecutionAttempt))
        assert attempt is not None
        attempt_id, wid = attempt.id, attempt.workspace_id
    return alice, base, attempt_id, wid, run, server, post


@pytest.mark.parametrize(
    "mode", ["closing", "revoked", "expired", "viewer", "late_expired", "unknown"]
)
def retained_test_real_api_completion_historical_authority_and_unknown_hold(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    mode: str,
) -> None:
    from app.publication import google_execution_completion as service
    from app.workspaces.models import Workspace

    alice, base, attempt, wid, run, server, post = first_attempt(
        customer_engine, configuration, tmp_path, monkeypatch, replicas, timeout=mode == "unknown"
    )
    session_key = digest(alice.cookies[SESSION_COOKIE])
    with Session(customer_engine) as db:
        session = db.get(CustomerSession, session_key)
        assert session is not None
        member = db.scalar(
            select(CustomerMembership).where(
                CustomerMembership.user_id == session.user_id,
                CustomerMembership.workspace_id == wid,
            )
        )
        assert member is not None
        if mode == "closing":
            workspace = db.get(Workspace, wid)
            assert workspace
            workspace.status = "closing"
        elif mode == "revoked":
            session.revoked_at = int(time.time())
        elif mode == "expired":
            session.expires_at = int(time.time()) - 1
        elif mode == "viewer":
            member.role = "viewer"
        db.commit()
    if mode == "late_expired":
        original = service._read

        def expire(db: Session, *args: Any, **kwargs: Any) -> Any:
            result = original(db, *args, **kwargs)
            session = db.get(CustomerSession, session_key)
            assert session
            session.expires_at = int(time.time()) - 1
            db.flush()
            return result

        monkeypatch.setattr(service, "_read", expire)
    response = alice.get(base + f"/attempts/{attempt}/receipt")
    expected = (
        401 if mode in {"revoked", "expired", "late_expired"} else 403 if mode == "viewer" else 200
    )
    assert response.status_code == expected, response.text
    if expected == 200:
        projection = response.json()["original_operation_completion"]
        assert projection["status"] == ("unavailable" if mode == "unknown" else "completed")
        assert projection["financial_finality"] == "unavailable"
        if mode == "unknown":
            assert projection["commitment"] is None
            server.timeout = False
            writes = server.posts
            post(f"/runs/{run['id']}/advance")
            assert server.posts == writes == 1
    with Session(customer_engine) as db:
        hold = db.scalar(select(ProviderExposureReservation))
        assert hold and hold.state == "held"
        assert db.scalar(select(func.count()).select_from(GoogleOriginalCompletion)) == (
            0 if mode == "unknown" else 1
        )


@pytest.mark.parametrize("mode", ["duplicate_json", "deep", "partial", "async"])
@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_real_wire_ambiguous_success_does_not_produce_capture(mode: str) -> None:
    from app.executors.google_publication import GooglePublicationHTTP
    from app.publication.google_execution_completion_contracts import GoogleCapturedCreationResponse

    from tests.test_google_publication_http import context, first

    def send(_: httpx.Request) -> httpx.Response:
        if mode == "duplicate_json":
            raw = (
                b'{"results":[],"results":[{'
                b'"resourceName":"customers/1234567890/campaignBudgets/1"}]}'
            )
        elif mode == "deep":
            raw = b'{"deep":' + b"[" * 1500 + b"0" + b"]" * 1500 + b"}"
        else:
            data = {"results": [{"resourceName": "customers/1234567890/campaignBudgets/1"}]}
            data["partialFailureError" if mode == "partial" else "operation"] = {}  # type: ignore[assignment]
            raw = json.dumps(data).encode()
        return httpx.Response(200, content=raw)

    request = first()
    result = GooglePublicationHTTP(transport=httpx.MockTransport(send)).apply_once(
        request, context(request), request.dispatched_at
    )
    assert result.outcome == "unknown"
    assert not isinstance(result, GoogleCapturedCreationResponse)


@pytest.mark.parametrize("mode", ["rollback", "duplicate", "late_unknown", "conflict"])
@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_capture_and_response_are_atomic_and_never_override_latest_receipt(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    from app.publication import coordinator as c
    from app.publication import google_execution_completion as evidence
    from app.publication.google_execution_completion_contracts import GoogleCapturedCreationResponse
    from app.publication.provider_contracts import BoundProviderRequest
    from app.publication.service import owner

    from tests.test_commerce_measurement import NOW
    from tests.test_provider_coordinator import GoogleServer, ready

    with Session(customer_engine) as db:
        server = GoogleServer()
        wid, run_id, actor, store, runtime = ready(db, configuration, tmp_path, server)
        claim = c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW)
        assert claim and isinstance(claim.request, BoundProviderRequest)
        response = runtime.google.apply_once(
            claim.request, runtime.google_context(claim.request), NOW
        )
        assert isinstance(response, GoogleCapturedCreationResponse)
        if mode == "rollback":
            original = evidence.capture_execution_response

            def fail(*args: Any, **kwargs: Any) -> None:
                original(*args, **kwargs)
                raise RuntimeError("controlled transaction interruption")

            monkeypatch.setattr(evidence, "capture_execution_response", fail)
            with pytest.raises(RuntimeError, match="controlled"):
                c.record_response(db, wid, claim.attempt_id, response, lambda: NOW)
            db.rollback()
            assert db.get(GoogleOriginalCompletion, claim.attempt_id) is None
            assert db.scalar(select(func.count()).select_from(ProviderExecutionResponse)) == 0
        else:
            c.record_response(db, wid, claim.attempt_id, response, lambda: NOW)
            c.record_response(db, wid, claim.attempt_id, response, lambda: NOW)
            if mode == "conflict":
                from app.publication.google_execution_completion_contracts import capture_success
                from fastapi import HTTPException

                resource = "customers/1234567890/campaignBudgets/9999"
                conflicting = GoogleCapturedCreationResponse(
                    request_digest=claim.request.digest(),
                    outcome="acknowledged",
                    resource_name=resource,
                    capture=capture_success(
                        claim.request, {"results": [{"resourceName": resource}]}
                    ),
                )
                with pytest.raises(HTTPException, match="immutable original"):
                    c.record_response(db, wid, claim.attempt_id, conflicting, lambda: NOW)
                db.rollback()
                assert db.scalar(select(func.count()).select_from(ProviderExecutionResponse)) == 1
            receipt = runtime.google.read_back(
                claim.request, response, runtime.google_context(claim.request), NOW
            )
            c.record_receipt(db, wid, claim.attempt_id, receipt, lambda: NOW)
            assert db.scalar(select(func.count()).select_from(GoogleOriginalCompletion)) == 1
            if mode == "late_unknown":
                c.record_receipt(
                    db, wid, claim.attempt_id, c.unknown(claim.request, NOW), lambda: NOW
                )
            result = evidence.read_execution_completion(
                db,
                wid,
                claim.attempt_id,
                actor,
                authorize=lambda: owner(db, wid, actor),
                clock=lambda: NOW,
            )
            assert result.status == ("unavailable" if mode == "late_unknown" else "completed")
        hold = db.scalar(select(ProviderExposureReservation))
        assert hold and hold.state == "held"
        assert server.posts == 1
