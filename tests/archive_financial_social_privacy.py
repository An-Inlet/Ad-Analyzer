"""Exact current request deltas for the closed two-brand archive source only."""

import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime
from typing import Any

from app.customers.access import CSRF_COOKIE, SESSION_COOKIE, TTL_SECONDS, digest
from app.lifecycle.archive import encoded
from app.lifecycle.contracts import LifecycleInputV1, LifecycleScopeV1
from app.shopify.security import utc
from fastapi.testclient import TestClient

from tests.archive_financial_social_retained_fixture import Rows, SourceIds


def same(actual: Rows, expected: Rows) -> None:
    for name in actual:
        assert actual[name] == expected[name], name


def stamp(value: Any, started: datetime, ended: datetime) -> None:
    assert isinstance(value, datetime) and started <= utc(value) <= ended


def uuid(value: Any) -> None:
    assert type(value) is str and re.fullmatch(r"[a-f0-9]{32}", value)


def login_delta(
    before: Rows,
    actual: Rows,
    ids: SourceIds,
    alice: TestClient,
    bob: TestClient,
    started: datetime,
    ended: datetime,
) -> None:
    expected = deepcopy(before)
    assert not before["customer_sessions"] and not before["customer_token_exchanges"]
    sessions = []
    for client, brand in ((alice, ids.brand_a), (bob, ids.brand_b)):
        identifier = digest(client.cookies[SESSION_COOKIE])
        row = next(r for r in actual["customer_sessions"] if r["digest"] == identifier)
        for field in ("created_at", "authenticated_at"):
            assert int(started.timestamp()) <= row[field] <= int(ended.timestamp())
        assert row == dict(
            digest=identifier,
            user_id=brand.actor_id,
            csrf_digest=digest(client.cookies[CSRF_COOKIE]),
            created_at=row["created_at"],
            authenticated_at=row["authenticated_at"],
            expires_at=row["created_at"] + TTL_SECONDS,
            revoked_at=None,
        )
        sessions.append(row)
    expected["customer_sessions"] = sorted(sessions, key=lambda r: r["digest"])
    exchanges = actual["customer_token_exchanges"]
    assert len(exchanges) == 2 and {r["digest"] for r in exchanges} == {
        digest("brand-a:1"),
        digest("brand-b:1"),
    }
    for row in exchanges:
        assert set(row) == {"digest", "expires_at"}
        assert int(started.timestamp()) + 3600 <= row["expires_at"] <= int(ended.timestamp()) + 3600
    expected["customer_token_exchanges"] = exchanges
    same(actual, expected)


def creation_delta(
    before: Rows,
    actual: Rows,
    ids: SourceIds,
    request_id: str,
    operation: str,
    started: datetime,
    ended: datetime,
    inventory_digest: str | None = None,
) -> None:
    expected = deepcopy(before)
    row = next(r for r in actual["customer_lifecycle_requests"] if r["id"] == request_id)
    uuid(request_id)
    uuid(row["fence"])
    stamp(row["created_at"], started, ended)
    body = LifecycleInputV1(
        scope=LifecycleScopeV1(workspace_id=ids.brand_a.workspace_id), operation=operation
    )
    expected_row = dict(
        id=request_id,
        workspace_id=ids.brand_a.workspace_id,
        requested_by=ids.brand_a.actor_id,
        operation=operation,
        key_digest=hashlib.sha256(
            ("archive" if operation == "export" else "closure").encode() + b"-replacement-social"
        ).hexdigest(),
        request_digest=hashlib.sha256(
            json.dumps(body.model_dump(), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        schema_version="inlet.lifecycle.request.v1",
        state="requested",
        revision=1,
        fence=row["fence"],
        disposition_policy=None,
        blockers=[]
        if operation == "export"
        else [blocker("retention_policy_unset", "lifecycle", "owner_policy")],
        created_at=row["created_at"],
        updated_at=row["created_at"],
    )
    expected["customer_lifecycle_requests"].append(expected_row)
    if operation == "close":
        assert inventory_digest and re.fullmatch(r"[a-f0-9]{64}", inventory_digest)
        expected["customer_lifecycle_steps"].append(
            dict(
                request_id=request_id,
                step_key="inventory",
                workspace_id=ids.brand_a.workspace_id,
                request_revision=1,
                fence=row["fence"],
                state="complete",
                attempts=1,
                lease_until=None,
                evidence_digest=inventory_digest,
            )
        )
    sort_lifecycle(expected)
    same(actual, expected)


def blocker(code: str, subsystem: str, resolution_kind: str) -> dict[str, str]:
    return dict(code=code, subsystem=subsystem, resolution_kind=resolution_kind)


def sort_lifecycle(rows: Rows) -> None:
    rows["customer_lifecycle_requests"].sort(key=lambda r: r["id"])
    rows["customer_lifecycle_steps"].sort(key=lambda r: (r["request_id"], r["step_key"]))


def download_delta(
    before: Rows,
    actual: Rows,
    request_id: str,
    manifest: dict[str, Any],
    started: datetime,
    ended: datetime,
) -> None:
    expected = deepcopy(before)
    row = next(r for r in expected["customer_lifecycle_requests"] if r["id"] == request_id)
    final = next(r for r in actual["customer_lifecycle_requests"] if r["id"] == request_id)
    uuid(final["fence"])
    assert final["fence"] != row["fence"]
    stamp(final["updated_at"], started, ended)
    assert utc(final["updated_at"]) == datetime.fromisoformat(manifest["snapshot_as_of"])
    row.update(
        revision=2,
        fence=final["fence"],
        state="archive_built",
        updated_at=final["updated_at"],
        blockers=[
            dict(
                code="export_snapshot",
                **{
                    key: manifest[key]
                    for key in (
                        "snapshot_revision",
                        "snapshot_as_of",
                        "supported_customer_data_complete",
                        "media_archive_complete",
                        "all_stored_workspace_data_complete",
                    )
                },
            )
        ],
    )
    expected["customer_lifecycle_steps"].append(
        dict(
            request_id=request_id,
            step_key="export_build",
            workspace_id=row["workspace_id"],
            request_revision=2,
            fence=row["fence"],
            state="complete",
            attempts=1,
            lease_until=None,
            evidence_digest=hashlib.sha256(encoded(manifest)).hexdigest(),
        )
    )
    sort_lifecycle(expected)
    same(actual, expected)


def closure_delta(
    before: Rows, actual: Rows, ids: SourceIds, request_id: str, started: datetime, ended: datetime
) -> None:
    expected = deepcopy(before)
    wid = ids.brand_a.workspace_id
    request = next(r for r in expected["customer_lifecycle_requests"] if r["id"] == request_id)
    final = next(r for r in actual["customer_lifecycle_requests"] if r["id"] == request_id)
    uuid(final["fence"])
    assert final["fence"] != request["fence"]
    stamp(final["updated_at"], started, ended)
    request.update(
        state="blocked",
        revision=2,
        fence=final["fence"],
        updated_at=final["updated_at"],
        blockers=[
            blocker("retention_policy_unset", "lifecycle", "owner_policy"),
            blocker("legacy_scope_unclassified", "inventory", "implementation"),
            blocker(
                "publication_unresolved", "provider_exposure_reservations", "operator_evidence"
            ),
            blocker("provider_revocation_unverified", "connections", "operator_evidence"),
            blocker("billing_unresolved", "billing", "operator_evidence"),
            blocker("worker_not_quiescent", "jobs", "implementation"),
        ],
    )
    changes: dict[str, dict[str, Any]] = {
        "workspaces": dict(status="closing"),
        "workspace_integrations": dict(status="revoked", secret_manager_reference=None),
        "crm_connections": dict(status="closed", secret_manager_reference=""),
        "google_customer_connections": dict(
            status="disconnected",
            encrypted_grant=None,
            cursor=None,
            staged={},
            next_attempt_at=None,
        ),
        "meta_connections": dict(
            status="reconnect_required", encrypted_credentials="", cursor=None, next_attempt_at=None
        ),
        "shopify_connections": dict(
            status="reconnect_required", encrypted_credentials="", cursor=None, next_attempt_at=None
        ),
        "spending_mandates": dict(paused=True),
        "provider_execution_mandates": dict(state="revoked"),
    }
    for table, fields in changes.items():
        for row in expected[table]:
            if row["id" if table == "workspaces" else "workspace_id"] != wid:
                continue
            row.update(fields)
            if table in {"workspaces", "workspace_integrations", "crm_connections"}:
                final_row = next(r for r in actual[table] if r["id"] == row["id"])
                stamp(final_row["updated_at"], started, ended)
                row["updated_at"] = final_row["updated_at"]
            if table == "workspaces":
                row["export_privacy_revision"] += 1
            if table in {"google_customer_connections", "meta_connections"}:
                row["generation"] += 1
    successor = next(
        r for r in expected["provider_execution_runs"] if r["id"] == ids.brand_a.successor_run_id
    )
    assert successor["canceled_at"] is None
    successor.update(state="canceled", canceled_at=final["updated_at"])
    value = dict(
        schema_version="inlet.lifecycle.queue_cancellation.v1",
        workspace_id=wid,
        request_id=request_id,
        revision=2,
        rows_canceled=0,
    )
    expected["customer_lifecycle_steps"].append(
        dict(
            request_id=request_id,
            step_key="analysis_queue_cancel",
            workspace_id=wid,
            request_revision=2,
            fence=request["fence"],
            attempts=1,
            state="complete",
            lease_until=None,
            evidence_digest=hashlib.sha256(
                json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        )
    )
    sort_lifecycle(expected)
    same(actual, expected)
