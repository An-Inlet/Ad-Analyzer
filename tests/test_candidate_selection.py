"""Owned target discovery→selection→v2 queue; actual mocked adapters, no mutations."""

from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.customers.models import CustomerMembership
from app.executors.google_optimization import GoogleOptimizationTransport
from app.executors.meta_optimization import MetaOptimizationTransport
from app.executors.tiktok_optimization import TikTokOptimizationTransport
from app.lifecycle.export_serializers import serialize
from app.optimization_candidates import selection as x
from app.optimization_candidates import service as s
from app.optimization_candidates.contracts import CandidateWork
from app.optimization_candidates.models import CandidateJob, CandidateResult
from app.optimization_candidates.selection_contracts import (
    CandidatePolicyRef,
    CandidateWorkV2,
    parse_work,
)
from app.publication.contracts import fingerprint
from app.publication.customer_optimization_contracts import (
    TargetCatalog,
    TargetOption,
    TargetRequest,
)
from app.publication.optimization_contracts import OptimizationContext
from app.settings import Settings
from app.workspaces.models import Workspace
from fastapi import HTTPException
from pydantic import SecretStr, ValidationError
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.candidate_read_retained_fixture import CandidateReadIds, load_candidate_read_fixture
from tests.candidate_read_retained_fixture import retained_candidate_case as retained_candidate_case
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_execution_session_authorizer import revoke
from tests.test_optimization_candidates import fixture
from tests.test_shopify_sales import configuration as configuration


def prepared(
    db: Session,
    config: Settings,
    path: Path,
    provider: str = "google_ads",
    *,
    retained_ids: CandidateReadIds | None = None,
) -> tuple[Any, ...]:
    principal, work, observation, _, candidate, server = (
        fixture(db, config, path, provider=provider)
        if retained_ids is None
        else load_candidate_read_fixture(db, retained_ids)
    )
    adapter = {
        "google_ads": GoogleOptimizationTransport,
        "meta_ads": MetaOptimizationTransport,
        "tiktok_ads": TikTokOptimizationTransport,
    }[provider](transport=httpx.MockTransport(server))

    def catalog(request, now):  # type: ignore[no-untyped-def]
        state = adapter.read_current(
            request.scope,
            work.scope.target,
            observation.state.money,
            observation.state.qualification_id,
            observation.state.qualification_revision,
            OptimizationContext(
                scope=request.scope,
                access_token=SecretStr("offline-token"),
                expires_at=NOW + timedelta(hours=1),
            ),
            now,
        )
        return TargetCatalog(
            request=request,
            observed_at=now,
            expires_at=now + timedelta(minutes=1),
            options=[
                TargetOption(label="Owned native owner", parent_label="Campaign", state=state)
            ],
            complete=True,
        )

    runtime = x.CandidateSelectionRuntime(
        candidate=candidate,
        catalog=catalog,
        source_fence_reader=lambda db, request, now: work.scope.source,
        clock=lambda: NOW,
    )
    ref = CandidatePolicyRef(policy_id=work.policy.policy_id, revision=work.policy.revision)
    return principal, work, observation, runtime, ref, server


@pytest.mark.parametrize("provider", ["google_ads", "meta_ads", "tiktok_ads"])
@pytest.mark.planning_boundary
def test_actual_discovery_to_v2_read_and_export(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    provider: str,
    retained_candidate_case: tuple[Engine, CandidateReadIds],
) -> None:
    customer_engine, ids = retained_candidate_case
    with Session(customer_engine) as db:
        principal, old, observation, runtime, ref, server = prepared(
            db, configuration, tmp_path, provider, retained_ids=ids
        )
        wid = old.scope.account.workspace_id
        batch, jobs = x.enqueue_candidate_selection(
            db, principal, wid, old.scope.mandate, ref, runtime
        )
        assert len(jobs) == 1 and not batch.blocked
        identifier = jobs[0].id
        value = s.owned_work(jobs[0])
        assert isinstance(value, CandidateWorkV2)
        assert value.selection.manifest_digest == batch.manifest_digest
        assert value.selection.authority == "none"
        _, again = x.enqueue_candidate_selection(
            db, principal, wid, old.scope.mandate, ref, runtime
        )
        assert again[0].id == identifier
        db.commit()
    assert s.process(customer_engine, wid, identifier, runtime.candidate) == "completed"
    assert len(server.writes if provider == "google_ads" else server.posts) == 0
    with Session(customer_engine) as db:
        mapping = db.execute(select(CandidateJob.__table__)).mappings().one()
        exported, missing = serialize(CandidateJob.__tablename__, dict(mapping))
        assert not missing and exported["work"]["schema_version"] == "inlet.candidate-work.v2"
        assert db.scalar(select(func.count()).select_from(CandidateResult)) == 1


@pytest.mark.planning_boundary
def test_old_v1_bytes_and_digest_unchanged(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    retained_candidate_case: tuple[Engine, CandidateReadIds],
) -> None:
    customer_engine, ids = retained_candidate_case
    with Session(customer_engine) as db:
        principal, old, _, runtime, _, _ = prepared(db, configuration, tmp_path, retained_ids=ids)
        raw = old.model_dump(mode="json")
        assert set(raw) == {"schema_version", "purpose", "scope", "policy"}
        expected = fingerprint("inlet.candidate-work.v1", raw)
        assert parse_work(raw).digest() == expected == old.digest()
        assert isinstance(parse_work(raw), CandidateWork)
        assert parse_work(raw).model_dump_json() == old.model_dump_json()
        row = s.enqueue(db, principal, old, runtime.candidate)
        assert row.input_digest == expected


@pytest.mark.parametrize("change", ["logout", "role", "privacy", "catalog", "expiry"])
@pytest.mark.planning_boundary
def test_changes_during_reads_admit_no_jobs(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    change: str,
    retained_candidate_case: tuple[Engine, CandidateReadIds],
) -> None:
    customer_engine, ids = retained_candidate_case
    with Session(customer_engine) as db:
        principal, work, _, runtime, ref, server = prepared(
            db, configuration, tmp_path, retained_ids=ids
        )
        wid, token = work.scope.account.workspace_id, principal.session.digest

        def source(db, request, now):  # type: ignore[no-untyped-def]
            if change == "logout":
                revoke(customer_engine, token)
            elif change == "role":
                membership = db.scalar(
                    select(CustomerMembership).where(CustomerMembership.workspace_id == wid)
                )
                assert membership
                membership.role = "viewer"
                db.commit()
            elif change == "privacy":
                workspace = db.get(Workspace, wid)
                assert workspace
                workspace.export_privacy_revision += 1
                db.commit()
            elif change == "catalog":
                server.budget["amountMicros"] = "60000000"
            return work.scope.source

        runtime = replace(runtime, source_fence_reader=source)
        if change == "expiry":
            ticks = [NOW]
            original = runtime.catalog

            def expired(request, now):  # type: ignore[no-untyped-def]
                result = original(request, NOW)
                ticks[0] = NOW + timedelta(minutes=2)
                return result

            runtime = replace(runtime, catalog=expired, clock=lambda: ticks[0])
        with pytest.raises((HTTPException, ValueError)):
            x.enqueue_candidate_selection(db, principal, wid, work.scope.mandate, ref, runtime)
        assert db.scalar(select(func.count()).select_from(CandidateJob)) == 0


@pytest.mark.planning_boundary
def test_unapproved_scope_and_tamper_block(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    retained_candidate_case: tuple[Engine, CandidateReadIds],
) -> None:
    customer_engine, ids = retained_candidate_case
    with Session(customer_engine) as db:
        principal, old, _, runtime, ref, _ = prepared(db, configuration, tmp_path, retained_ids=ids)
        batch = x.plan_candidate_reads(
            db, principal, old.scope.account.workspace_id, old.scope.mandate, ref, runtime
        )
        raw = batch.selected[0].model_dump(mode="json")
        raw["selection"]["scope_digest"] = "0" * 64
        with pytest.raises(ValidationError):
            parse_work(raw)
        with pytest.raises(HTTPException):
            x.enqueue_candidate_selection(
                db, principal, old.scope.account.workspace_id + 100, old.scope.mandate, ref, runtime
            )
        assert db.scalar(select(func.count()).select_from(CandidateJob)) == 0


@pytest.mark.parametrize("change", ["role", "privacy", "catalog_expiry"])
@pytest.mark.planning_boundary
def test_post_read_workspace_lock_wait_revalidates(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
    retained_candidate_case: tuple[Engine, CandidateReadIds],
) -> None:
    customer_engine, ids = retained_candidate_case
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    if customer_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row locks required")
    read_done, allow_return, entering_lock = Event(), Event(), Event()
    with Session(customer_engine) as db:
        principal, work, _, runtime, ref, _ = prepared(
            db, configuration, tmp_path, retained_ids=ids
        )
        wid, actor, token = (
            work.scope.account.workspace_id,
            principal.user.id,
            principal.session.digest,
        )
    clock = [NOW]
    original_authorize = s.authorize

    def guarded(db, principal, wid, runtime):  # type: ignore[no-untyped-def]
        if allow_return.is_set():
            entering_lock.set()
        original_authorize(db, principal, wid, runtime)

    monkeypatch.setattr(s, "authorize", guarded)

    def fence(db, request, now):  # type: ignore[no-untyped-def]
        read_done.set()
        assert allow_return.wait(10)
        return work.scope.source

    runtime = replace(runtime, source_fence_reader=fence, clock=lambda: clock[0])

    def worker() -> None:
        from app.customers.access import CustomerPrincipal
        from app.customers.models import CustomerSession, CustomerUser

        with Session(customer_engine) as db:
            user, session = db.get(CustomerUser, actor), db.get(CustomerSession, token)
            assert user and session
            x.enqueue_candidate_selection(
                db, CustomerPrincipal(user, session), wid, work.scope.mandate, ref, runtime
            )

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(worker)
        assert read_done.wait(10)
        with Session(customer_engine) as db:
            workspace = db.scalar(select(Workspace).where(Workspace.id == wid).with_for_update())
            assert workspace
            if change == "role":
                member = db.scalar(
                    select(CustomerMembership).where(CustomerMembership.workspace_id == wid)
                )
                assert member
                member.role = "viewer"
            elif change == "privacy":
                workspace.export_privacy_revision += 1
            allow_return.set()
            assert entering_lock.wait(10)
            if change == "catalog_expiry":
                clock[0] = NOW + timedelta(minutes=2)
            db.commit()
        with pytest.raises(HTTPException):
            future.result(timeout=10)
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(CandidateJob)) == 0


@pytest.mark.planning_boundary
def test_partial_insert_failure_rolls_back_batch(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    retained_candidate_case: tuple[Engine, CandidateReadIds],
) -> None:
    customer_engine, ids = retained_candidate_case
    with Session(customer_engine) as db:
        principal, work, _, runtime, ref, _ = prepared(
            db, configuration, tmp_path, retained_ids=ids
        )
        original = s._insert_checked

        def failure(db, principal, work, runtime):  # type: ignore[no-untyped-def]
            original(db, principal, work, runtime)
            assert db.scalar(select(func.count()).select_from(CandidateJob)) == 1
            raise RuntimeError("controlled failure after flushed insertion")

        monkeypatch.setattr(s, "_insert_checked", failure)
        with pytest.raises(RuntimeError, match="controlled failure"):
            x.enqueue_candidate_selection(
                db, principal, work.scope.account.workspace_id, work.scope.mandate, ref, runtime
            )
        assert db.scalar(select(func.count()).select_from(CandidateJob)) == 0


@pytest.mark.planning_boundary
def test_owner_selection_never_substitutes_child_or_conflicting_owner(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    retained_candidate_case: tuple[Engine, CandidateReadIds],
) -> None:
    customer_engine, ids = retained_candidate_case
    from app.publication.optimization_contracts import BudgetOwnerRef, OptimizationTarget

    with Session(customer_engine) as db:
        _, work, observation, runtime, _, _ = prepared(
            db, configuration, tmp_path, "meta_ads", retained_ids=ids
        )
        state = observation.state
        campaign = OptimizationTarget(kind="campaign", external_id="5", campaign_id="5")
        owner = BudgetOwnerRef(
            provider="meta_ads",
            owner=campaign,
            mode="campaign_pool",
            affected_targets=[campaign, state.target],
            topology_digest="d" * 64,
        )
        child_state = state.model_copy(update={"budget_owner": owner})
        request = TargetRequest(
            scope=work.scope.account,
            goal_id=work.scope.goal_id,
            goal_revision=work.scope.goal_revision,
            goal_digest=work.scope.goal_digest,
        )
        child = TargetOption(label="Child", parent_label="Parent", state=child_state)
        catalog = TargetCatalog(
            request=request,
            observed_at=NOW,
            expires_at=NOW + timedelta(minutes=1),
            options=[child],
            complete=True,
        )
        assert x.owner_option(catalog, owner.target_set_digest()) == (
            None,
            "approved_owner_unavailable",
        )
        parent = TargetOption(
            label="Parent",
            parent_label="Parent",
            state=child_state.model_copy(update={"target": campaign}),
        )
        alias = parent.model_copy(update={"label": "Another label"})
        catalog = catalog.model_copy(update={"options": [child, parent, alias]})
        chosen, reason = x.owner_option(catalog, owner.target_set_digest())
        assert chosen and chosen.state.target == campaign and reason == ""
        reverse = catalog.model_copy(update={"options": list(reversed(catalog.options))})
        assert x.owner_option(reverse, owner.target_set_digest())[0] == chosen
        assert x.catalog_digest(reverse) == x.catalog_digest(catalog)
        drift = parent.model_copy(
            update={
                "state": parent.state.model_copy(update={"unaffected_settings_digest": "f" * 64})
            }
        )
        catalog = catalog.model_copy(update={"options": [parent, drift]})
        assert x.owner_option(catalog, owner.target_set_digest()) == (
            None,
            "contradictory_owner_snapshots",
        )


@pytest.mark.planning_boundary
def test_expiry_during_insert_rolls_back(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    retained_candidate_case: tuple[Engine, CandidateReadIds],
) -> None:
    customer_engine, ids = retained_candidate_case
    with Session(customer_engine) as db:
        principal, work, _, runtime, ref, _ = prepared(
            db, configuration, tmp_path, retained_ids=ids
        )
        clock = [NOW]
        runtime = replace(runtime, clock=lambda: clock[0])
        original = s._insert_checked

        def delayed(db, principal, work, candidate):  # type: ignore[no-untyped-def]
            row = original(db, principal, work, candidate)
            clock[0] = NOW + timedelta(minutes=2)
            return row

        monkeypatch.setattr(s, "_insert_checked", delayed)
        with pytest.raises(HTTPException, match="expired during insert"):
            x.enqueue_candidate_selection(
                db, principal, work.scope.account.workspace_id, work.scope.mandate, ref, runtime
            )
        assert db.scalar(select(func.count()).select_from(CandidateJob)) == 0
