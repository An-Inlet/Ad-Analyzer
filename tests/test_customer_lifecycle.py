"""Offline workspace lifecycle foundation: scope, receipt races, fences and omissions."""

import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount, Campaign
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.database.session import Base
from app.lifecycle.contracts import LifecycleInputV1, LifecycleScopeV1
from app.lifecycle.inventory import export_section, inventory, verify_registry
from app.lifecycle.models import LifecycleRequest
from app.lifecycle.registry import PRIVATE_STAGING_TABLES, TABLES
from app.lifecycle.service import begin, claim_inventory, finish_inventory
from app.workspaces.models import Workspace, WorkspaceConfiguration
from fastapi import HTTPException
from sqlalchemy import Column, Engine, Integer, Table, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine

NOW = datetime.now(UTC)
KEY = "same-key-for-scope-tests"


def seed(db: Session, suffix: str = "one") -> tuple[CustomerPrincipal, int]:
    user = CustomerUser(
        id=uuid4().hex,
        issuer=FakeProvider.issuer,
        subject=suffix,
        email=f"{suffix}@example.test",
        status="active",
    )
    db.add(user)
    workspace = Workspace(slug=suffix, name=suffix, client_name=suffix, status="active")
    db.add(workspace)
    db.flush()
    session = CustomerSession(
        digest=uuid4().hex * 2,
        user_id=user.id,
        csrf_digest="f" * 64,
        created_at=int(time.time()),
        expires_at=int(time.time()) + 3600,
        authenticated_at=int(time.time()),
    )
    db.add(session)
    db.add(
        CustomerMembership(
            user_id=user.id, workspace_id=workspace.id, role="owner", status="active"
        )
    )
    db.commit()
    return CustomerPrincipal(user, session), workspace.id


def test_all_tables_classified_and_new_tables_fail_closed(customer_engine: Engine) -> None:
    verify_registry()
    table = Table(
        "unclassified_future_table", Base.metadata, Column("id", Integer, primary_key=True)
    )
    try:
        with pytest.raises(ValueError, match="classification incomplete"):
            verify_registry()
    finally:
        Base.metadata.remove(table)


def test_every_scoped_section_executes_without_querying_global_rows(
    customer_engine: Engine,
) -> None:
    with Session(customer_engine) as db:
        _, wid = seed(db)
        scope = LifecycleScopeV1(workspace_id=wid)
        manifest = inventory(db, scope)
        assert len(manifest["sections"]) == len(TABLES)
        assert manifest["disposition_policy"] is None
        assert manifest["closure_complete"] is False
        for section in manifest["sections"]:
            if section["scope"] in {"unclassified", "identity_global", "platform_global"}:
                assert section["count"] is None
                with pytest.raises(ValueError):
                    export_section(db, scope, section["table"])
            elif section["table"] in PRIVATE_STAGING_TABLES:
                # Owned private read staging is erasable/inventoried, never an export section.
                with pytest.raises(ValueError):
                    export_section(db, scope, section["table"])
            else:
                result = export_section(db, scope, section["table"])
                assert result["complete_export"] is False
                assert result["media_archive_complete"] is False
        assert TABLES["publication_receipts"].protected
        assert TABLES["mandate_actions"].protected


def test_two_tenant_parent_scope_and_secret_projection(customer_engine: Engine) -> None:
    with Session(customer_engine) as db:
        for suffix in ["one", "two"]:
            _, wid = seed(db, suffix)
            if suffix == "one":
                owned = wid
            db.add(WorkspaceConfiguration(workspace_id=wid, analysis={"secret": "never-export"}))
            account = AdvertisingAccount(
                workspace_id=wid,
                platform=AdvertisingPlatform.GOOGLE_ADS,
                external_account_id=suffix,
                name=suffix,
                currency_code="USD",
            )
            db.add(account)
            db.flush()
            db.add(
                Campaign(
                    account_id=account.id,
                    platform=AdvertisingPlatform.GOOGLE_ADS,
                    external_campaign_id=suffix,
                    name=suffix,
                )
            )
        db.commit()
        scope = LifecycleScopeV1(workspace_id=owned)
        result = export_section(db, scope, "campaigns")
        assert [row["name"] for row in result["rows"]] == ["one"]
        config = export_section(db, scope, "workspace_configurations")
        assert "analysis" in config["omitted_fields"]
        assert "never-export" not in str(config)
        db.add(
            Campaign(
                account_id=account.id,
                platform=AdvertisingPlatform.GOOGLE_ADS,
                external_campaign_id="second",
                name="second",
            )
        )
        db.commit()
        limited = export_section(db, LifecycleScopeV1(workspace_id=wid), "campaigns", limit=1)
        assert limited["truncated"] is True and len(limited["rows"]) == 1


def test_owner_receipt_replay_foreign_denial_and_revocation(customer_engine: Engine) -> None:
    with Session(customer_engine) as db:
        principal, wid = seed(db)
        foreign, other = seed(db, "two")
        body = LifecycleInputV1(scope=LifecycleScopeV1(workspace_id=wid), operation="close")
        first = begin(db, principal, FakeProvider(), body, KEY, NOW)
        db.commit()
        assert begin(db, principal, FakeProvider(), body, KEY, NOW).id == first.id
        db.commit()
        with pytest.raises(HTTPException) as denied:
            begin(db, foreign, FakeProvider(), body, KEY, NOW)
        assert denied.value.status_code == 404
        db.rollback()
        second = begin(
            db,
            foreign,
            FakeProvider(),
            body.model_copy(update={"scope": LifecycleScopeV1(workspace_id=other)}),
            KEY,
            NOW,
        )
        db.commit()
        assert second.id != first.id
        assert first.disposition_policy is None and first.state == "requested"
        assert first.blockers[0]["code"] == "retention_policy_unset"
        # Package1 records intent without modifying access, grants, sessions or billing.
        assert principal.session.revoked_at is None and foreign.session.revoked_at is None
        assert db.get(Workspace, wid).status == "active"  # type: ignore[union-attr]
        member = db.get(CustomerMembership, (principal.user.id, wid))
        assert member is not None
        member.role = "admin"
        db.commit()
        with pytest.raises(HTTPException) as role:
            begin(db, principal, FakeProvider(), body, KEY, NOW)
        assert role.value.status_code == 403
        db.rollback()
        member.role, member.status = "owner", "suspended"
        db.commit()
        with pytest.raises(HTTPException):
            begin(db, principal, FakeProvider(), body, KEY, NOW)


def test_expired_worker_fence_cannot_complete_or_claim_export_delivery(
    customer_engine: Engine,
) -> None:
    with Session(customer_engine) as db:
        principal, wid = seed(db)
        row = begin(
            db,
            principal,
            FakeProvider(),
            LifecycleInputV1(scope=LifecycleScopeV1(workspace_id=wid), operation="export"),
            KEY,
            NOW,
        )
        db.commit()
        _, first = claim_inventory(db, wid, row.id, 1, NOW)
        db.commit()
        with pytest.raises(HTTPException):
            claim_inventory(db, wid, row.id, 1, NOW + timedelta(seconds=1))
        db.rollback()
        _, newer = claim_inventory(db, wid, row.id, 1, NOW + timedelta(seconds=61))
        db.commit()
        with pytest.raises(HTTPException):
            finish_inventory(db, wid, row.id, 1, first, "a" * 64, NOW + timedelta(seconds=62))
        db.rollback()
        finish_inventory(db, wid, row.id, 1, newer, "b" * 64, NOW + timedelta(seconds=62))
        db.commit()
        finish_inventory(db, wid, row.id, 1, newer, "b" * 64, NOW + timedelta(seconds=63))
        db.commit()
        assert row.state == "requested"  # Inventory success is not successful export delivery.
        with pytest.raises(HTTPException):
            finish_inventory(db, wid, row.id, 1, newer, "c" * 64, NOW + timedelta(seconds=64))


def test_concurrent_owner_receipts_are_atomic(customer_engine: Engine) -> None:
    from concurrent.futures import ThreadPoolExecutor

    if customer_engine.dialect.name != "postgresql":
        pytest.skip("row lock concurrency requires PostgreSQL")
    with Session(customer_engine) as db:
        principal, wid = seed(db)
        uid, sid = principal.user.id, principal.session.digest

    def create() -> str:
        with Session(customer_engine) as db:
            user, session = db.get(CustomerUser, uid), db.get(CustomerSession, sid)
            assert user is not None and session is not None
            row = begin(
                db,
                CustomerPrincipal(user, session),
                FakeProvider(),
                LifecycleInputV1(scope=LifecycleScopeV1(workspace_id=wid), operation="close"),
                KEY,
                NOW,
            )
            db.commit()
            return row.id

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _: create(), range(2)))
    assert results[0] == results[1]
    with Session(customer_engine) as db:
        assert len(db.scalars(select(LifecycleRequest)).all()) == 1


def test_policy_and_identity_inputs_are_not_accepted() -> None:
    from pydantic import ValidationError

    for extra in ["requested_by", "disposition_policy", "external_verified", "purge"]:
        with pytest.raises(ValidationError):
            LifecycleInputV1.model_validate(
                {
                    "scope": {"workspace_id": 1},
                    "operation": "close",
                    extra: "unsafe",
                }
            )
    with pytest.raises(ValidationError):
        LifecycleScopeV1.model_validate({"kind": "identity", "workspace_id": 1})


def test_mismatched_replay_and_foreign_fence_fail_closed(customer_engine: Engine) -> None:
    with Session(customer_engine) as db:
        principal, wid = seed(db)
        _, other = seed(db, "two")
        body = LifecycleInputV1(scope=LifecycleScopeV1(workspace_id=wid), operation="close")
        row = begin(db, principal, FakeProvider(), body, KEY, NOW)
        db.commit()
        row.request_digest = "0" * 64
        db.commit()
        with pytest.raises(HTTPException) as mismatch:
            begin(db, principal, FakeProvider(), body, KEY, NOW)
        assert mismatch.value.status_code == 409
        db.rollback()
        with pytest.raises(HTTPException) as foreign:
            claim_inventory(db, other, row.id, 1, NOW)
        assert foreign.value.status_code == 404


def test_section_byte_bound_is_explicit(
    customer_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.lifecycle import inventory as module

    with Session(customer_engine) as db:
        _, wid = seed(db)
        monkeypatch.setattr(module, "MAX_SECTION_BYTES", 1)
        result = export_section(db, LifecycleScopeV1(workspace_id=wid), "workspaces")
        assert result["rows"] == [] and result["truncated"] is True
        assert result["complete_export"] is False
        monkeypatch.setattr(module, "MAX_ROW_BYTES", 1)
        with pytest.raises(ValueError, match="row exceeds bound"):
            export_section(db, LifecycleScopeV1(workspace_id=wid), "workspaces")


def test_unknown_publication_accounting_remains_protected(customer_engine: Engine) -> None:
    from app.mandates.models import Mandate, MandateAction
    from app.publication.models import PublicationPlanRecord, PublicationStepRecord

    with Session(customer_engine) as db:
        principal, wid = seed(db)
        mandate = Mandate(
            id=uuid4().hex,
            workspace_id=wid,
            revision=1,
            starts_at=NOW,
            ends_at=NOW + timedelta(days=1),
            state="approved",
            paused=False,
            reserved_micros=100,
        )
        db.add(mandate)
        db.flush()
        action = MandateAction(
            id=uuid4().hex,
            mandate_id=mandate.id,
            workspace_id=wid,
            draft={},
            digest="a" * 64,
            state="outcome_unknown",
        )
        db.add(action)
        db.flush()
        plan = PublicationPlanRecord(
            id=uuid4().hex,
            workspace_id=wid,
            action_id=action.id,
            digest="b" * 64,
            document={},
            state="outcome_unknown",
        )
        db.add(plan)
        db.flush()
        db.add(
            PublicationStepRecord(
                plan_id=plan.id, step_id="campaign", workspace_id=wid, state="unknown"
            )
        )
        db.commit()
        scope = LifecycleScopeV1(workspace_id=wid)
        evidence = inventory(db, scope)
        assert sum(b["code"] == "publication_unresolved" for b in evidence["blockers"]) == 2
        begin(
            db,
            principal,
            FakeProvider(),
            LifecycleInputV1(scope=scope, operation="close"),
            KEY,
            NOW,
        )
        db.commit()
        db.refresh(mandate)
        db.refresh(action)
        assert mandate.reserved_micros == 100 and action.state == "outcome_unknown"
        assert db.get(PublicationStepRecord, (plan.id, "campaign")) is not None
