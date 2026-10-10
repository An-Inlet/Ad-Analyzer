"""Gate actual closed source before current privacy graph assertions are implemented."""

import hashlib
import json
import re
import time
from collections.abc import Generator
from contextlib import ExitStack, closing
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from app.customers.access import CSRF_COOKIE, TTL_SECONDS
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerUser
from app.database.session import get_db
from app.lifecycle.contracts import LifecycleInputV1, LifecycleScopeV1
from app.main import app
from app.publication.coordinator import read_owned_outcome_receipt
from app.settings import settings
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_customer_identity import ORIGIN, FakeProvider, login
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_two_brand_pilot import ok
from tests.two_brand_closure_graph import closure_delta, same, snapshot
from tests.two_brand_receipt_contracts import TwoBrandReceiptSourceV1
from tests.two_brand_receipt_retained_fixture import produce, source_engine
from tests.two_brand_receipt_validation import validate_source


def test_exact_two_brand_retained_source(customer_engine: Engine, tmp_path: Path) -> None:
    with source_engine(customer_engine, tmp_path / "two-brand") as engine:
        ids = produce(engine, tmp_path / "two-brand")
        assert ids.brand_a.workspace_id != ids.brand_b.workspace_id
        assert ids.counts.held_reservations == 1
        validate_source(engine, ids, tmp_path / "two-brand/original/media")
        altered = ids.model_dump()
        altered["brand_a"]["shopify_connection_id"] = ids.brand_b.shopify_connection_id
        with pytest.raises(AssertionError, match="shopify_connections"):
            validate_source(
                engine,
                TwoBrandReceiptSourceV1.model_validate(altered),
                tmp_path / "two-brand/original/media",
            )


def test_current_closure_over_exact_two_brand_source(
    customer_engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        source_engine(customer_engine, tmp_path / "two-brand") as engine,
        ExitStack() as client_lifetime,
    ):
        ids = produce(engine, tmp_path / "two-brand")
        validate_source(engine, ids, tmp_path / "two-brand/original/media")
        before = snapshot(engine)

        def no_provider_io(*args: object, **kwargs: object) -> None:
            raise AssertionError("Current retained closure must not call a provider")

        monkeypatch.setattr(httpx.HTTPTransport, "handle_request", no_provider_io)
        monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", no_provider_io)
        identity = FakeProvider()

        def database() -> Generator[Session, None, None]:
            with Session(engine) as db:
                yield db

        monkeypatch.setattr(
            app, "dependency_overrides", {get_db: database, get_identity_provider: lambda: identity}
        )
        monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)
        monkeypatch.setattr(settings, "billing_required", False)
        clients = [
            client_lifetime.enter_context(closing(TestClient(app, base_url=ORIGIN)))
            for _ in range(2)
        ]
        for index, (brand, client) in enumerate(
            zip((ids.brand_a, ids.brand_b), clients, strict=True)
        ):
            prior = snapshot(engine)
            with Session(engine) as db:
                user = db.get(CustomerUser, brand.actor_id)
                assert user is not None
                identity.issuer, identity.email = user.issuer, user.email
                subject = user.subject
            lower = int(time.time())
            assert login(client, subject + f":current-two-brand-{index}") == brand.actor_id
            upper = int(time.time())
            after = snapshot(engine)
            expected = deepcopy(prior)
            new = [
                r
                for r in after["customer_sessions"]
                if r["digest"] not in {x["digest"] for x in prior["customer_sessions"]}
            ]
            assert len(new) == 1
            row = new[0]
            assert re.fullmatch(r"[a-f0-9]{64}", row["digest"])
            assert re.fullmatch(r"[a-f0-9]{64}", row["csrf_digest"])
            assert row["user_id"] == brand.actor_id and row["revoked_at"] is None
            assert (
                lower <= row["created_at"] <= upper
                and row["expires_at"] == row["created_at"] + TTL_SECONDS
            )
            assert lower <= row["authenticated_at"] <= upper
            expected["customer_sessions"].extend(new)
            # Login uses one actual integer now for receipt expiry housekeeping.
            retained = [
                r for r in prior["customer_token_exchanges"] if r["expires_at"] > row["created_at"]
            ]
            added = [
                r
                for r in after["customer_token_exchanges"]
                if r["digest"] not in {x["digest"] for x in prior["customer_token_exchanges"]}
            ]
            assert len(added) == 1 and lower + 3600 <= added[0]["expires_at"] <= upper + 3600
            expected["customer_token_exchanges"] = retained + added
            same(expected, after)
        for old in before["customer_sessions"]:
            assert old in snapshot(engine)["customer_sessions"]
        a, b = ids.brand_a, ids.brand_b
        with Session(engine) as db:
            assert read_owned_outcome_receipt(
                db, a.workspace_id, ids.execution.owned_attempt_id, a.actor_id
            )
            for wid, actor in ((a.workspace_id, b.actor_id), (b.workspace_id, b.actor_id)):
                with pytest.raises(HTTPException):
                    read_owned_outcome_receipt(db, wid, ids.execution.owned_attempt_id, actor)
                db.rollback()
        root = f"/api/customer/v1/workspaces/{a.workspace_id}"
        h = {"Origin": ORIGIN, "X-CSRF-Token": clients[0].cookies[CSRF_COOKIE]}
        prior = snapshot(engine)
        preview_lower = datetime.now(UTC)
        preview = ok(
            clients[0].post(
                root + "/closure-preview",
                headers={**h, "Idempotency-Key": "two-brand-current-closure"},
                json={},
            )
        )
        preview_upper = datetime.now(UTC)
        after = snapshot(engine)
        expected = deepcopy(prior)
        req = after["customer_lifecycle_requests"]
        steps = after["customer_lifecycle_steps"]
        assert not prior["customer_lifecycle_requests"] and not prior["customer_lifecycle_steps"]
        assert len(req) == len(steps) == 1
        row = req[0]
        assert re.fullmatch(r"[a-f0-9]{32}", row["id"])
        assert re.fullmatch(r"[a-f0-9]{32}", row["fence"])
        assert preview_lower <= row["created_at"] == row["updated_at"] <= preview_upper
        body = LifecycleInputV1(
            scope=LifecycleScopeV1(workspace_id=a.workspace_id), operation="close"
        )
        assert row == dict(
            id=preview["request_id"],
            workspace_id=a.workspace_id,
            requested_by=a.actor_id,
            operation="close",
            schema_version="inlet.lifecycle.request.v1",
            state="requested",
            revision=1,
            disposition_policy=None,
            key_digest=hashlib.sha256(b"two-brand-current-closure").hexdigest(),
            request_digest=hashlib.sha256(
                json.dumps(body.model_dump(), sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            fence=row["fence"],
            created_at=row["created_at"],
            updated_at=row["created_at"],
            blockers=[
                dict(
                    code="retention_policy_unset",
                    subsystem="lifecycle",
                    resolution_kind="owner_policy",
                )
            ],
        )
        assert steps == [
            dict(
                request_id=row["id"],
                step_key="inventory",
                workspace_id=a.workspace_id,
                request_revision=1,
                fence=row["fence"],
                state="complete",
                attempts=1,
                lease_until=None,
                evidence_digest=preview["inventory_digest"],
            )
        ]
        expected["customer_lifecycle_requests"] = req
        expected["customer_lifecycle_steps"] = steps
        same(expected, after)
        closure_lower = datetime.now(UTC)
        closed = ok(
            clients[0].post(
                root + f"/closures/{preview['request_id']}/confirm",
                headers=h,
                json=dict(
                    expected_revision=preview["revision"],
                    inventory_digest=preview["inventory_digest"],
                    confirm_workspace_id=a.workspace_id,
                ),
            )
        )
        closure_upper = datetime.now(UTC)
        assert closed["closed"] is False and closed["data_erased"] is False
        final = snapshot(engine)
        closure_delta(after, final, ids, preview["request_id"], closure_lower, closure_upper)
        # Reject unrelated changes rather than overlooking them in expected deltas.
        for table, field, value in (
            ("provider_execution_receipts", "digest", "0" * 64),
            ("provider_exposure_reservations", "state", "settled"),
            ("customer_sessions", "revoked_at", 1),
        ):
            altered = deepcopy(final)
            altered[table][0][field] = value
            with pytest.raises(AssertionError, match=table):
                closure_delta(
                    after, altered, ids, preview["request_id"], closure_lower, closure_upper
                )
        altered = deepcopy(final)
        other = next(
            r for r in altered["workspace_integrations"] if r["workspace_id"] == b.workspace_id
        )
        other["status"] = "revoked"
        with pytest.raises(AssertionError, match="workspace_integrations"):
            closure_delta(after, altered, ids, preview["request_id"], closure_lower, closure_upper)
        assert clients[0].get(root + f"/closures/{preview['request_id']}").status_code == 200
        assert clients[1].get(root + f"/closures/{preview['request_id']}").status_code == 404
        foreign = f"/api/customer/v1/workspaces/{b.workspace_id}"
        assert clients[1].get(foreign + f"/goals/{b.goal_id}").status_code == 200
        assert clients[1].get(foreign + "/sources/hubspot").status_code == 200
        with Session(engine) as db:
            assert read_owned_outcome_receipt(
                db, a.workspace_id, ids.execution.owned_attempt_id, a.actor_id
            )
        same(final, snapshot(engine))
