"""Actual bounded HTTP -> owned DB publication -> strict export and erasure."""

import copy
import json
from datetime import date, timedelta
from typing import Any

import httpx
import pytest
from app.commerce.evidence import digest, read_publication
from app.commerce.independent_contracts import ScanRequest, ScanUnavailable
from app.commerce.independent_owned import OwnedAcquisition
from app.commerce.models import CommerceEvidenceState, CommerceMeasurementPublication, CommerceStore
from app.commerce.privacy import purge_measurements
from app.commerce.publication_contracts import IndependentManifest, parse_publication
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.lifecycle.export_serializers import serialize
from app.outcomes import descriptive
from app.outcomes.owned import observe
from app.outcomes.reconciliation import collect_owned_reconciliations
from app.outcomes.reconciliation_contracts import ReconciliationRequest
from app.settings import Settings
from app.shopify.privacy import process_event
from app.shopify.security import ShopifyError
from app.shopify.service import ConnectionService
from app.workspaces.models import Workspace
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from tests.candidate_current_fixture import current_candidate_read as current_candidate_read
from tests.candidate_read_retained_fixture import CandidateReadIds, load_candidate_read_fixture
from tests.test_commerce_measurement import NOW
from tests.test_customer_exports import export_engine as export_engine
from tests.test_customer_identity import FakeProvider, login
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_descriptive_comparisons import prepared
from tests.test_independent_acquisition import Fixture
from tests.test_shopify_sales import SHOP
from tests.test_shopify_sales import configuration as configuration


def ready(
    engine: Engine, config: Settings, clients: tuple[TestClient, TestClient, FakeProvider] | None
) -> Any:
    if clients is None:
        from tests.test_customer_lifecycle import seed

        with Session(engine) as db:
            seeded, _ = seed(db)
            actor = seeded.user.id
        provider = FakeProvider()
    else:
        client, _, provider = clients
        actor = login(client, "independent-publication-owner:1")
    with Session(engine) as db:
        if engine.dialect.name == "sqlite":
            db.execute(text("PRAGMA foreign_keys=ON"))
        wid, body = prepared(db, config)
        row = db.get(CommerceMeasurementPublication, body.publication_id)
        assert row is not None
        sid = row.store_id
        db.add(CustomerMembership(user_id=actor, workspace_id=wid, role="owner", status="active"))
        db.commit()
        user = db.get(CustomerUser, actor)
        session = db.scalar(select(CustomerSession).where(CustomerSession.user_id == actor))
        assert user is not None and session is not None
        principal = CustomerPrincipal(user, session)
        service = OwnedAcquisition(
            lambda: Session(engine),
            principal,
            provider,
            config,
            environment="contract_test",
            clock=lambda: NOW,
        )
        token = session.digest
    request = service.capture(wid, sid, body.goal_id, 1, date(2026, 10, 1), date(2026, 10, 2))
    fixture, transport = transport_for(request)
    return service, request, transport, fixture, body, token


def transport_for(request: ScanRequest) -> tuple[Fixture, httpx.MockTransport]:
    fixture = Fixture()
    fixture.request = request
    fixture.now = NOW

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.host == SHOP
        assert request.headers["x-shopify-access-token"]
        forwarded = httpx.Request(
            "POST",
            "https://synthetic.myshopify.com/admin/api/2026-07/graphql.json",
            headers={"x-shopify-access-token": "synthetic-private-token"},
            content=request.content,
        )
        response = fixture.handle(forwarded)
        value = response.json()
        if "shop" in value["data"]:
            value["data"]["shop"]["id"] = "gid://shopify/Shop/123"
        return httpx.Response(response.status_code, json=value)

    return fixture, httpx.MockTransport(handle)


def test_real_acquisition_persist_load_and_v1_coexistence(
    customer_engine: Engine,
    configuration: Settings,
    replicas: tuple[TestClient, TestClient, FakeProvider],
) -> None:
    service, request, transport, _, body, _ = ready(customer_engine, configuration, replicas)
    with Session(customer_engine) as db:
        original = db.get(CommerceMeasurementPublication, body.publication_id)
        assert original is not None
        old_raw, old_digest = copy.deepcopy(original.manifest), original.manifest_digest
    identifier = service.acquire_and_publish(request, transport=transport)
    document = service.load(request.scope.workspace_id, identifier)
    assert isinstance(document, IndependentManifest)
    assert document.acquisition.days[0].value_micros == -10_000_000
    assert document.source_watermark is None and document.correction_status == "unresolved"
    assert document.maturity == "unqualified"
    with Session(customer_engine) as db:
        original = db.get(CommerceMeasurementPublication, body.publication_id)
        row = db.get(CommerceMeasurementPublication, identifier)
        assert original is not None and row is not None
        assert original.manifest == old_raw and original.manifest_digest == old_digest
        assert (
            read_publication(db, request.scope.workspace_id, request.scope.store_id, now=NOW)[
                "publication_id"
            ]
            == original.id
        )
        assert row.publication_revision > original.publication_revision
        assert (
            descriptive.compare(
                db, request.scope.workspace_id, body, lambda: None, lambda: NOW
            ).status
            == "available_as_of"
        )
        observations = collect_owned_reconciliations(
            db,
            request.scope.workspace_id,
            ReconciliationRequest(
                goal_id=body.goal_id,
                expected_goal_revision=1,
                latest_publication_id=body.publication_id,
                start=body.before_start,
                end=body.before_end,
            ),
            lambda: None,
            lambda: NOW,
        )
        assert len(observations.observations) == 1
        assert observations.independent_reconciliation == "unqualified"
        store = db.get(CommerceStore, request.scope.store_id)
        assert store is not None
        with pytest.raises(HTTPException, match="unsupported"):
            observe(row, store, request.start, request.end)
        for entry in (original, row):
            raw = {c.name: getattr(entry, c.name) for c in entry.__table__.columns}
            exported, missing = serialize("commerce_measurement_publications", raw)
            assert not missing and exported["manifest"] == entry.manifest
            assert exported["manifest_digest"] == digest(entry.manifest)
        db.commit()
    assert service._publish(document.acquisition) == identifier


@pytest.mark.parametrize("change", ["logout", "role", "privacy", "generation", "closure", "token"])
def test_actual_database_change_during_http_prevents_publication(
    customer_engine: Engine,
    configuration: Settings,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    change: str,
) -> None:
    service, request, transport, fixture, body, session_id = ready(
        customer_engine, configuration, replicas
    )

    def mutate(query: str) -> None:
        if "InletAgreements" not in query:
            return
        with Session(customer_engine) as db:
            if change == "logout":
                row = db.get(CustomerSession, session_id)
                assert row is not None
                row.revoked_at = 1
            elif change == "role":
                membership = db.get(
                    CustomerMembership, (service.original.user_id, request.scope.workspace_id)
                )
                assert membership is not None
                membership.role = "viewer"
            elif change == "privacy":
                process_event(db, configuration, "orders/delete", SHOP, {"id": 1}, NOW)
            elif change == "generation":
                state = db.get(CommerceEvidenceState, request.scope.store_id)
                assert state is not None
                state.generation += 1
            elif change == "closure":
                workspace = db.get(Workspace, request.scope.workspace_id)
                assert workspace is not None
                workspace.status = "closing"
            else:
                native = ConnectionService(db, configuration).get(request.scope.workspace_id)
                assert native is not None
                native.connected_at += timedelta(seconds=1)
            db.commit()

    fixture.after = mutate
    with pytest.raises(ScanUnavailable):
        service.acquire_and_publish(request, transport=transport)
    with Session(customer_engine) as db:
        rows = list(db.scalars(select(CommerceMeasurementPublication)))
        assert all(row.id == body.publication_id for row in rows)


@pytest.mark.parametrize("change", ["privacy", "disconnect", "retention", "closing_privacy"])
def test_source_wide_deletion_removes_both_versions(
    customer_engine: Engine,
    configuration: Settings,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    change: str,
) -> None:
    service, request, transport, _, body, _ = ready(customer_engine, configuration, replicas)
    identifier = service.acquire_and_publish(request, transport=transport)
    with Session(customer_engine) as db:
        if change == "closing_privacy":
            workspace = db.get(Workspace, request.scope.workspace_id)
            assert workspace is not None
            workspace.status = "closing"
            db.commit()
        if change in {"privacy", "closing_privacy"}:
            process_event(db, configuration, "orders/delete", SHOP, {"id": 1}, NOW)
        elif change == "disconnect":
            ConnectionService(db, configuration).disconnect(request.scope.workspace_id, "owner")
        else:
            purge_measurements(db, NOW + timedelta(days=400))
        db.commit()
        assert db.get(CommerceMeasurementPublication, identifier) is None
        assert db.get(CommerceMeasurementPublication, body.publication_id) is None
    with pytest.raises((HTTPException, ScanUnavailable, ShopifyError)):
        service.load(request.scope.workspace_id, identifier)


def test_export_rejects_unknown_or_forged_v2_json(
    customer_engine: Engine,
    configuration: Settings,
    replicas: tuple[TestClient, TestClient, FakeProvider],
) -> None:
    service, request, transport, _, _, _ = ready(customer_engine, configuration, replicas)
    identifier = service.acquire_and_publish(request, transport=transport)
    with Session(customer_engine) as db:
        row = db.get(CommerceMeasurementPublication, identifier)
        assert row is not None
        baseline = {c.name: getattr(row, c.name) for c in row.__table__.columns}
        for field, value in (
            ("unknown", "private"),
            ("workspace_id", row.workspace_id + 1),
            ("maturity", "operational_as_of"),
            ("source_watermark", NOW.isoformat()),
        ):
            raw = copy.deepcopy(baseline)
            raw["manifest"][field] = value
            raw["manifest_digest"] = digest(raw["manifest"])
            exported, missing = serialize("commerce_measurement_publications", raw)
            assert "manifest" in missing and "manifest" not in exported
        row.completion_digest = "e" * 64
        with pytest.raises(ValueError):
            parse_publication(row)


def test_actual_archive_contains_typed_v2_and_original_v1(
    export_engine: Engine,
    configuration: Settings,
    tmp_path: Any,
) -> None:
    from app.campaign_review.storage import LocalMediaStore
    from app.lifecycle.contracts import LifecycleInputV1, LifecycleScopeV1
    from app.lifecycle.exports import Authority
    from app.lifecycle.service import begin

    from tests.test_customer_exports import build, unpack
    from tests.test_customer_lifecycle import KEY

    service, request, transport, _, body, session_id = ready(export_engine, configuration, None)
    identifier = service.acquire_and_publish(request, transport=transport)
    with Session(export_engine) as db:
        user = db.get(CustomerUser, service.original.user_id)
        session = db.get(CustomerSession, session_id)
        assert user is not None and session is not None
        principal = CustomerPrincipal(user, session)
        row = begin(
            db,
            principal,
            service.identity,
            LifecycleInputV1(
                scope=LifecycleScopeV1(workspace_id=request.scope.workspace_id),
                operation="export",
            ),
            KEY,
            NOW,
        )
        db.commit()
        authority = Authority(
            export_engine, principal, service.identity, request.scope.workspace_id, row.id
        )
    authority.claim()
    file, manifest = build(export_engine, authority, LocalMediaStore(tmp_path / "media"))
    try:
        _, files = unpack(file)
        key = next(k for k in files if k.endswith("commerce_measurement_publications.jsonl"))
        rows = [json.loads(line) for line in files[key].splitlines()]
        assert {r["id"] for r in rows} == {body.publication_id, identifier}
        independent = next(r for r in rows if r["id"] == identifier)
        assert independent["manifest"]["maturity"] == "unqualified"
        assert independent["manifest"]["source_watermark"] is None
        assert not any(b"synthetic-private-token" in contents for contents in files.values())
        section = next(s for s in manifest["sections"] if s["path"] == key)
        assert not section["unsupported_fields"]
    finally:
        file.close()


@pytest.mark.parametrize("change", ["retention", "provider", "source_revision"])
def test_fresh_authority_after_http_invalidates_without_persisting(
    customer_engine: Engine,
    configuration: Settings,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    change: str,
) -> None:
    service, request, transport, fixture, body, _ = ready(customer_engine, configuration, replicas)
    clock = [NOW]
    service.clock = lambda: clock[0]

    def changed(query: str) -> None:
        if "InletAgreements" not in query:
            return
        if change == "retention":
            clock[0] = NOW + timedelta(days=400)
        elif change == "provider":
            replicas[2].disabled.add(service.original.subject)
        else:
            with Session(customer_engine) as db:
                store = db.get(CommerceStore, request.scope.store_id)
                assert store is not None
                store.revision += 1
                db.commit()

    fixture.after = changed
    with pytest.raises(ScanUnavailable):
        service.acquire_and_publish(request, transport=transport)
    with Session(customer_engine) as db:
        assert list(db.scalars(select(CommerceMeasurementPublication.id))) == [body.publication_id]


def test_final_atomic_persistence_rechecks_request_and_original_session(
    customer_engine: Engine,
    configuration: Settings,
    replicas: tuple[TestClient, TestClient, FakeProvider],
) -> None:
    from app.commerce.independent import IndependentAcquirer

    service, request, transport, _, _, session_id = ready(customer_engine, configuration, replicas)
    completion = IndependentAcquirer(
        service.authority, transport=transport, clock=lambda: NOW
    ).acquire(request)
    with Session(customer_engine) as db:
        session = db.get(CustomerSession, session_id)
        assert session is not None
        session.revoked_at = 1
        db.commit()
    with pytest.raises(HTTPException) as denied:
        service._publish(completion)
    assert denied.value.status_code == 401


@pytest.mark.parametrize("change", ["source_revision", "privacy"])
@pytest.mark.planning_boundary
def test_v2_does_not_displace_candidate_v1_but_actual_changes_still_deny(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Any,
    change: str,
    current_candidate_read: tuple[Engine, CandidateReadIds],
) -> None:
    from app.optimization_candidates.service import source_current

    customer_engine, source_ids = current_candidate_read

    with Session(customer_engine) as db:
        principal, work, _, _, runtime, _ = load_candidate_read_fixture(db, source_ids)
        source_current(db, work.scope, principal.user.id)
        actor = principal.user.id
        service = OwnedAcquisition(
            lambda: Session(customer_engine),
            principal,
            runtime.identity,
            configuration,
            environment="contract_test",
            clock=lambda: NOW,
        )
        db.commit()
    scope = work.scope
    request = service.capture(
        scope.account.workspace_id,
        scope.source.store_id,
        scope.goal_id,
        scope.goal_revision,
        date(2026, 10, 1),
        date(2026, 10, 2),
    )
    _, transport = transport_for(request)
    identifier = service.acquire_and_publish(request, transport=transport)
    with Session(customer_engine) as db:
        source_current(db, scope, actor)
        row = db.get(CommerceMeasurementPublication, identifier)
        assert row is not None and row.publication_revision > scope.source.publication_revision
        if change == "source_revision":
            store = db.get(CommerceStore, scope.source.store_id)
            assert store is not None
            store.revision += 1
        else:
            process_event(db, configuration, "orders/delete", SHOP, {"id": 1}, NOW)
        db.commit()
        with pytest.raises(HTTPException) as changed:
            source_current(db, scope, actor)
        assert changed.value.status_code == 409


def test_real_v2_provenance_persists_with_insufficient_assessment_and_erases(
    customer_engine: Engine, configuration: Settings, tmp_path: Any
) -> None:
    import time
    from uuid import uuid4

    from app.outcome_feedback.models import V3Assessment
    from app.outcome_feedback.service import EvidenceReference, persist_assessment
    from app.outcomes.owned_v3 import OwnedV3Request, assess_owned_v3
    from app.publication.service import owner
    from sqlalchemy.orm import sessionmaker

    from tests.test_owned_outcomes import evidence

    with Session(customer_engine) as db:
        wid, actor, body, _, _ = evidence(db, configuration, tmp_path)
        user = db.get(CustomerUser, actor)
        assert user is not None
        user.issuer = FakeProvider.issuer
        session = CustomerSession(
            digest=uuid4().hex * 2,
            user_id=actor,
            csrf_digest="f" * 64,
            created_at=int(time.time()),
            authenticated_at=int(time.time()),
            expires_at=int(time.time()) + 3600,
        )
        db.add(session)
        db.commit()
        service = OwnedAcquisition(
            lambda: Session(customer_engine),
            CustomerPrincipal(user, session),
            FakeProvider(),
            configuration,
            environment="contract_test",
            clock=lambda: NOW,
        )
    request = OwnedV3Request.model_validate(body.model_dump(exclude={"policy_id"}))

    def authorize(db: Session) -> None:
        owner(db, wid, actor)

    value = assess_owned_v3(
        sessionmaker(customer_engine), wid, actor, request, authorize, lambda: NOW
    )
    scope = value.context.scope
    scan = service.capture(
        wid,
        scope.store_id,
        scope.goal_id,
        scope.goal_revision,
        date(2026, 10, 1),
        date(2026, 10, 2),
    )
    _, transport = transport_for(scan)
    identifier = service.acquire_and_publish(scan, transport=transport)
    with Session(customer_engine) as db:
        rows = [
            db.get(CommerceMeasurementPublication, key)
            for key in (value.publication_id, identifier)
        ]
        assert all(rows)
        refs = tuple(
            EvidenceReference(
                publication_id=row.id,
                manifest_digest=row.manifest_digest,
                completion_digest=row.completion_digest,
            )
            for row in rows
            if row
        )
        stored = persist_assessment(db, wid, actor, value, refs, authorize, lambda: NOW)
        assert stored.document["status"] == "insufficient"
        # A retained acquisition is provenance, never evidence of settled maturity.
        from app.outcomes.maturity import OperationalMaturityResult

        unqualified = OperationalMaturityResult(
            status="insufficient",
            environment="contract_test",
            policy_digest=None,
            evidence_digest=None,
            context_digest=digest(value.context.model_dump(mode="json")),
            evaluated_at=NOW,
            supporting_completions=(refs[1].completion_digest,),
            reasons=("fixture_unqualified",),
        )
        forged = value.model_copy(update={"before_maturity": unqualified})
        with pytest.raises(HTTPException, match="maturity unavailable"):
            persist_assessment(db, wid, actor, forged, refs, authorize, lambda: NOW)
        saved_id = stored.id
        db.commit()
        independent = db.get(CommerceMeasurementPublication, identifier)
        assert independent is not None
        db.delete(independent)
        db.commit()
        db.expire_all()
        assert db.get(V3Assessment, saved_id) is None
