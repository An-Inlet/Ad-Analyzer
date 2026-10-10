"""Exact full-row comparator; no table-wide financial or session exemptions."""

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from app.database.session import Base
from app.lifecycle.local_work import evidence_digest
from sqlalchemy import Engine, select

from tests.two_brand_receipt_contracts import TwoBrandReceiptSourceV1


def normalized(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    if isinstance(value, dict):
        return {k: normalized(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalized(v) for v in value]
    return value


def snapshot(engine: Engine) -> dict[str, list[dict[str, Any]]]:
    with engine.connect() as db:
        return {
            name: [normalized(dict(r)) for r in db.execute(select(table)).mappings()]
            for name, table in Base.metadata.tables.items()
        }


def ordered(graph: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    return {k: sorted(v, key=lambda r: repr(sorted(r.items()))) for k, v in graph.items()}


def same(a: dict[str, list[dict[str, Any]]], b: dict[str, list[dict[str, Any]]]) -> None:
    assert set(a) == set(b)
    for table in a:
        assert ordered({table: a[table]}) == ordered({table: b[table]}), table


def closure_delta(
    before: dict[str, list[dict[str, Any]]],
    after: dict[str, list[dict[str, Any]]],
    ids: TwoBrandReceiptSourceV1,
    request_id: str,
    lower: datetime,
    upper: datetime,
) -> None:
    expected = deepcopy(before)
    wid = ids.brand_a.workspace_id
    request = next(r for r in after["customer_lifecycle_requests"] if r["id"] == request_id)
    now = request["updated_at"]
    assert lower <= now <= upper
    old = next(r for r in expected["customer_lifecycle_requests"] if r["id"] == request_id)
    assert old["state"] == "requested" and old["revision"] == 1
    assert len(request["fence"]) == 32 and request["fence"] != old["fence"]
    blockers = [
        dict(code=c, subsystem=s, resolution_kind=k)
        for c, s, k in [
            ("retention_policy_unset", "lifecycle", "owner_policy"),
            ("legacy_scope_unclassified", "inventory", "implementation"),
            ("publication_unresolved", "provider_exposure_reservations", "operator_evidence"),
            ("provider_revocation_unverified", "connections", "operator_evidence"),
            ("billing_unresolved", "billing", "operator_evidence"),
            ("worker_not_quiescent", "jobs", "implementation"),
        ]
    ]
    assert sorted(request["blockers"], key=repr) == sorted(blockers, key=repr)
    old.update(
        state="blocked",
        revision=2,
        fence=request["fence"],
        updated_at=now,
        blockers=request["blockers"],
    )
    for r in expected["workspaces"]:
        if r["id"] == wid:
            assert r["status"] == "active"
            actual_workspace = next(w for w in after["workspaces"] if w["id"] == wid)
            assert lower <= actual_workspace["updated_at"] <= upper
            r["updated_at"] = actual_workspace["updated_at"]
            r["status"] = "closing"
            r["export_privacy_revision"] += 1
    changes: dict[str, dict[str, Any]] = {
        "workspace_integrations": dict(status="revoked", secret_manager_reference=None),
        "customer_source_connections": dict(
            status="disconnected",
            encrypted_grant=None,
            cursor=None,
            staged={},
            next_attempt_at=None,
        ),
        "google_customer_connections": dict(
            status="disconnected",
            encrypted_grant=None,
            cursor=None,
            staged={},
            next_attempt_at=None,
        ),
        "shopify_connections": dict(
            status="reconnect_required", encrypted_credentials="", cursor=None, next_attempt_at=None
        ),
        "spending_mandates": dict(paused=True),
        "provider_execution_mandates": dict(state="revoked"),
    }
    assert len([r for r in expected["workspace_integrations"] if r["workspace_id"] == wid]) == 3
    for table, values in changes.items():
        for r in expected[table]:
            if r["workspace_id"] == wid:
                if table == "workspace_integrations":
                    actual = next(v for v in after[table] if v["id"] == r["id"])
                    assert lower <= actual["updated_at"] <= upper
                    r["updated_at"] = actual["updated_at"]
                r.update(deepcopy(values))
                if table in {"google_customer_connections", "customer_source_connections"}:
                    r["generation"] += 1
    for r in expected["provider_execution_runs"]:
        if r["workspace_id"] == wid and r["canceled_at"] is None:
            r.update(state="canceled", canceled_at=now)
    expected["customer_source_authorizations"] = [
        r for r in expected["customer_source_authorizations"] if r["workspace_id"] != wid
    ]
    expected["customer_lifecycle_steps"].append(
        dict(
            request_id=request_id,
            step_key="analysis_queue_cancel",
            workspace_id=wid,
            request_revision=2,
            fence=request["fence"],
            state="complete",
            attempts=1,
            lease_until=None,
            evidence_digest=evidence_digest(
                dict(
                    schema_version="inlet.lifecycle.queue_cancellation.v1",
                    workspace_id=wid,
                    request_id=request_id,
                    revision=2,
                    rows_canceled=0,
                )
            ),
        )
    )
    same(expected, after)
