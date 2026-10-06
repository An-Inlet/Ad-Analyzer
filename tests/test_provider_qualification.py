import json
from datetime import timedelta
from typing import Any
from uuid import uuid4

import httpx
import pytest
from app.campaign_review import service as source_reviews
from app.campaign_review.storage import LocalMediaStore
from app.customers.models import CustomerMembership, CustomerUser
from app.executors.google_publication import GooglePublicationHTTP, GooglePublicationUnavailable
from app.google_connections.models import GoogleCustomerConnection
from app.mandates.models import MandateAction
from app.publication import provider_service as s
from app.publication.google_qualification import qualify_google
from app.publication.provider_contracts import (
    GoogleSearchTotalPublicationFields,
    ProviderContext,
    ProviderPublicationReview,
)
from app.publication.provider_models import ProviderQualificationRecord, ProviderReviewRecord
from app.settings import Settings
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_campaign_review import definition
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_action_plans import setup
from tests.test_provider_publication_contracts import review
from tests.test_shopify_sales import configuration as configuration


def response_rows() -> dict[str, dict[str, Any]]:
    return {
        "customer": {
            "id": "1234567890",
            "currencyCode": "USD",
            "timeZone": "UTC",
            "status": "ENABLED",
        },
        "customConversionGoal": {
            "resourceName": "customers/1234567890/customConversionGoals/42",
            "status": "ENABLED",
            "conversionActions": ["customers/1234567890/conversionActions/43"],
        },
        "conversionAction": {
            "resourceName": "customers/1234567890/conversionActions/43",
            "status": "ENABLED",
            "category": "PURCHASE",
            "type": "WEBPAGE",
        },
        "geoTargetConstant": {
            "resourceName": "geoTargetConstants/2840",
            "countryCode": "US",
            "targetType": "Country",
            "status": "ENABLED",
        },
        "languageConstant": {
            "resourceName": "languageConstants/1000",
            "code": "en",
            "targetable": True,
        },
    }


def adapter(rows: dict[str, dict[str, Any]]) -> GooglePublicationHTTP:
    def send(raw: httpx.Request) -> httpx.Response:
        assert raw.url.path.endswith("googleAds:search")
        query = json.loads(raw.content)["query"]
        table = query.split(" FROM ")[1].split()[0]
        key = table.split("_")[0] + "".join(part.title() for part in table.split("_")[1:])
        return httpx.Response(200, json={"results": [{key: rows[key]}]})

    return GooglePublicationHTTP(transport=httpx.MockTransport(send))


def ctx(r: ProviderPublicationReview) -> ProviderContext:
    return ProviderContext(
        scope=r.scope,
        login_customer_id=r.configuration.login_customer_id,
        access_token=SecretStr("mock-only"),
        expires_at=NOW + timedelta(hours=1),
    )


def test_actual_read_qualification_binds_inputs_and_expires() -> None:
    r = review()
    proof = qualify_google(r, ctx(r), adapter(response_rows()), NOW)
    assert proof.binding_digest == r.configuration_binding()
    assert proof.expires_at == NOW + timedelta(minutes=5)
    data = r.model_dump()
    data.update(qualification=proof.model_dump(), qualification_blockers=[])
    assert ProviderPublicationReview.model_validate(data).qualification is not None
    data["configuration"]["search_partners"] = True
    with pytest.raises(ValueError):
        ProviderPublicationReview.model_validate(data)


@pytest.mark.parametrize(
    "row,field,value",
    [
        ("customer", "currencyCode", "GBP"),
        ("customer", "timeZone", "America/New_York"),
        ("customer", "id", "9999999999"),
        ("customConversionGoal", "conversionActions", []),
        ("conversionAction", "category", "PAGE_VIEW"),
        ("conversionAction", "status", "REMOVED"),
        ("geoTargetConstant", "countryCode", "GB"),
        ("languageConstant", "targetable", False),
    ],
)
def test_unqualified_provider_configuration_rejected(row: str, field: str, value: Any) -> None:
    rows = response_rows()
    rows[row][field] = value
    r = review()
    with pytest.raises(GooglePublicationUnavailable):
        qualify_google(r, ctx(r), adapter(rows), NOW)


def seeded(
    db: Session, settings: Settings, path: Any, *, total_budget: bool = False
) -> tuple[int, str, str, LocalMediaStore]:
    mandate, scope, _ = setup(db, settings, days=10 if total_budget else 1)
    actor = uuid4().hex
    db.add(CustomerUser(id=actor, issuer="mock", subject=actor, email="mock@example.invalid"))
    db.flush()
    db.add(CustomerMembership(user_id=actor, workspace_id=mandate.workspace_id, role="owner"))
    db.commit()
    d = definition(db, mandate, scope).model_copy(
        update={
            "starts_at": NOW - timedelta(hours=1),
            "ends_at": NOW + timedelta(days=9 if total_budget else 0, hours=23, seconds=-1),
            "budget_micros": 40,
        }
    )
    store = LocalMediaStore(path)
    revision = source_reviews.revise(db, mandate.workspace_id, d, actor, store, NOW)
    source_reviews.approve(
        db,
        mandate.workspace_id,
        revision.draft_id,
        revision.revision,
        revision.digest,
        actor,
        store,
        NOW,
    )
    return mandate.workspace_id, revision.draft_id, actor, store


def prepare(
    db: Session,
    wid: int,
    draft: str,
    actor: str,
    store: LocalMediaStore,
    now: Any = NOW,
    *,
    total_budget: bool = False,
) -> ProviderReviewRecord:
    fields = review().configuration.model_copy(
        update={
            "reservation_micros": 40,
            "daily_budget_micros": 20,
            "account_timezone": "Pacific/Pago_Pago",
        }
    )
    if total_budget:
        raw = fields.model_dump()
        raw.pop("daily_budget_micros")
        raw.update(
            kind="google_search_total_v25_v1",
            total_budget_micros=40,
            budget_semantics="native_total_budget_not_portfolio_proof",
        )
        total_fields = GoogleSearchTotalPublicationFields.model_validate(raw)
    rows = response_rows()
    rows["customer"]["timeZone"] = "Pacific/Pago_Pago"
    return s.prepare_google(
        db,
        wid,
        draft,
        total_fields if total_budget else fields,
        actor,
        store,
        adapter(rows),
        lambda scope: ProviderContext(
            scope=scope,
            login_customer_id=None,
            access_token=SecretStr("mock"),
            expires_at=now + timedelta(hours=1),
        ),
        lambda: now,
    )


def test_persist_exact_review_approve_but_simulation_never_production_authority(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Any,
) -> None:
    with Session(customer_engine) as db:
        wid, draft, actor, store = seeded(db, configuration, tmp_path)
        row = prepare(db, wid, draft, actor, store)
        before = row.review
        approval = s.approve(
            db, wid, row.id, row.review_digest, row.plan_digest, actor, store, lambda: NOW
        )
        assert approval.review_id == row.id
        assert not s.view(row)["publication_eligible"]
        with pytest.raises(HTTPException, match="production publication mandate"):
            s.publication_authority(db, wid, row.id, actor, store, lambda: NOW)
        db.rollback()
        assert db.scalar(select(func.count()).select_from(MandateAction)) == 0
        newer = prepare(db, wid, draft, actor, store, NOW + timedelta(seconds=1))
        assert newer.id != row.id and row.review == before
        assert db.scalar(select(func.count()).select_from(ProviderQualificationRecord)) == 2


@pytest.mark.parametrize("change", ["expiry", "generation", "owner", "digest", "workspace"])
def test_review_approval_rechecks_current_authority(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Any,
    change: str,
) -> None:
    with Session(customer_engine) as db:
        wid, draft, actor, store = seeded(db, configuration, tmp_path)
        row = prepare(db, wid, draft, actor, store)
        now, digest = NOW, row.review_digest
        if change == "expiry":
            now += timedelta(minutes=6)
        elif change == "generation":
            native = db.scalar(
                select(GoogleCustomerConnection).where(GoogleCustomerConnection.workspace_id == wid)
            )
            assert native is not None
            native.generation += 1
            db.commit()
        elif change == "owner":
            membership = db.scalar(
                select(CustomerMembership).where(CustomerMembership.user_id == actor)
            )
            assert membership is not None
            membership.status = "suspended"
            db.commit()
        elif change == "digest":
            digest = "e" * 64
        else:
            wid += 999
        with pytest.raises(HTTPException):
            s.approve(db, wid, row.id, digest, row.plan_digest, actor, store, lambda: now)


def test_reconnect_during_read_cannot_persist_qualification(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Any,
) -> None:
    with Session(customer_engine) as db:
        wid, draft, actor, store = seeded(db, configuration, tmp_path)
        fields = review().configuration.model_copy(
            update={
                "reservation_micros": 40,
                "daily_budget_micros": 20,
                "account_timezone": "Pacific/Pago_Pago",
            }
        )
        rows = response_rows()
        rows["customer"]["timeZone"] = "Pacific/Pago_Pago"
        inner = adapter(rows)
        calls = 0

        def send(raw: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                with Session(customer_engine) as other:
                    native = other.scalar(
                        select(GoogleCustomerConnection).where(
                            GoogleCustomerConnection.workspace_id == wid
                        )
                    )
                    assert native is not None
                    native.generation += 1
                    other.commit()
            assert inner.transport is not None
            return inner.transport.handle_request(raw)

        with pytest.raises(HTTPException):
            s.prepare_google(
                db,
                wid,
                draft,
                fields,
                actor,
                store,
                GooglePublicationHTTP(transport=httpx.MockTransport(send)),
                lambda scope: ProviderContext(
                    scope=scope,
                    login_customer_id=None,
                    access_token=SecretStr("mock"),
                    expires_at=NOW + timedelta(hours=1),
                ),
                lambda: NOW,
            )
        db.rollback()
        assert db.scalar(select(func.count()).select_from(ProviderQualificationRecord)) == 0
        assert db.scalar(select(func.count()).select_from(ProviderReviewRecord)) == 0


def test_empty_blockers_need_exact_fresh_server_proof() -> None:
    r = review()
    data = r.model_dump()
    data["qualification_blockers"] = []
    with pytest.raises(ValueError):
        ProviderPublicationReview.model_validate(data)
    assert "qualification" not in r.model_dump()  # preserve existing unqualified review hashes
    proof = qualify_google(r, ctx(r), adapter(response_rows()), NOW)
    data["qualification"] = proof.model_dump()
    data["qualification"]["expires_at"] = NOW + timedelta(minutes=6)
    with pytest.raises(ValueError):
        ProviderPublicationReview.model_validate(data)


def test_populated_provider_migration_roundtrip(
    monkeypatch: pytest.MonkeyPatch,
    configuration: Settings,
    tmp_path: Any,
) -> None:
    import os

    from alembic import command
    from alembic.config import Config
    from app.settings import settings
    from scripts.reset_disposable_postgres import validate_disposable_url
    from sqlalchemy import create_engine, make_url, text

    if (
        not os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL")
        or os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") != "true"
    ):
        pytest.skip("explicit disposable PostgreSQL required")
    url = validate_disposable_url()
    schema = "provider_review_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
    engine = create_engine(scoped)
    monkeypatch.setattr(settings, "database_url", scoped.render_as_string(hide_password=False))
    config = Config("alembic.ini")
    try:
        command.upgrade(config, "head")
        with Session(engine) as db:
            wid, draft, actor, store = seeded(db, configuration, tmp_path)
        command.downgrade(config, "20261006_0040")
        command.upgrade(config, "head")
        with Session(engine) as db:
            row = prepare(db, wid, draft, actor, store)
            s.approve(
                db, wid, row.id, row.review_digest, row.plan_digest, actor, store, lambda: NOW
            )
            assert db.scalar(select(func.count()).select_from(ProviderReviewRecord)) == 1
        command.downgrade(config, "20261006_0040")
        command.upgrade(config, "head")
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(ProviderReviewRecord)) == 0
            assert db.get(CustomerUser, actor) is not None
            row = prepare(db, wid, draft, actor, store)
            assert row.source_revision == 1
    finally:
        engine.dispose()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_database_rejects_cross_workspace_qualification_reference(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Any,
) -> None:
    from app.workspaces.models import Workspace
    from sqlalchemy.exc import IntegrityError

    if customer_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL composite foreign-key guarantee")
    with Session(customer_engine) as db:
        wid, draft, actor, store = seeded(db, configuration, tmp_path)
        row = prepare(db, wid, draft, actor, store)
        other = Workspace(slug="foreign", name="Foreign", client_name="Foreign", status="active")
        db.add(other)
        db.commit()
        with pytest.raises(IntegrityError), db.begin_nested():
            db.add(
                ProviderReviewRecord(
                    id=uuid4().hex,
                    workspace_id=other.id,
                    qualification_id=row.qualification_id,
                    draft_id=row.draft_id,
                    source_revision=row.source_revision,
                    review_digest=row.review_digest,
                    plan_digest=row.plan_digest,
                    review=row.review,
                    plan=row.plan,
                    created_by=actor,
                    created_at=NOW,
                )
            )
            db.flush()


@pytest.mark.parametrize("operation", ["prepare", "approve"])
@pytest.mark.parametrize("lock_kind", ["workspace", "mandate", "native"])
def test_expiry_while_waiting_for_lifecycle_lock(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    lock_kind: str,
) -> None:
    """A real PostgreSQL blocker crosses expiry; no timing/sleep assumption decides it."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from time import monotonic, sleep

    from app.mandates.models import Mandate
    from app.publication.provider_models import ProviderReviewApproval
    from app.workspaces.models import Workspace
    from sqlalchemy import text

    if customer_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock regression")
    with Session(customer_engine) as db:
        wid, draft, actor, store = seeded(db, configuration, tmp_path)
        row = prepare(db, wid, draft, actor, store) if operation == "approve" else None
        row_id = row.id if row else ""
        review_digest = row.review_digest if row else ""
        plan_digest = row.plan_digest if row else ""
    ready, proceed = Event(), Event()
    now = [NOW if operation == "prepare" else NOW + timedelta(minutes=5, seconds=-1)]
    original = s.current_review
    calls = 0
    backend = [0]

    def barrier(*args: Any, **kwargs: Any) -> ProviderPublicationReview:
        nonlocal calls
        calls += 1
        if calls == (2 if operation == "prepare" else 1):
            ready.set()
            assert proceed.wait(10)
            backend[0] = int(args[0].scalar(text("select pg_backend_pid()")))
        return original(*args, **kwargs)

    if operation == "approve":
        monkeypatch.setattr(s, "current_review", barrier)

    def authorize(db: Session, workspace_id: int, actor_id: str) -> None:
        nonlocal calls
        from app.publication.execution_authorization import owner_authorizer

        calls += 1
        if calls == 2:
            ready.set()
            assert proceed.wait(10)
            backend[0] = int(db.scalar(text("select pg_backend_pid()")))
        owner_authorizer(db, workspace_id, actor_id)

    def attempt() -> None:
        with Session(customer_engine) as db:
            if operation == "approve":
                s.approve(db, wid, row_id, review_digest, plan_digest, actor, store, lambda: now[0])
            else:
                fields = review().configuration.model_copy(
                    update={
                        "reservation_micros": 40,
                        "daily_budget_micros": 20,
                        "account_timezone": "Pacific/Pago_Pago",
                    }
                )
                rows = response_rows()
                rows["customer"]["timeZone"] = "Pacific/Pago_Pago"
                s.prepare_google(
                    db,
                    wid,
                    draft,
                    fields,
                    actor,
                    store,
                    adapter(rows),
                    lambda scope: ProviderContext(
                        scope=scope,
                        login_customer_id=None,
                        access_token=SecretStr("mock"),
                        expires_at=NOW + timedelta(hours=1),
                    ),
                    lambda: now[0],
                    authorize=authorize,
                )

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(attempt)
        try:
            assert ready.wait(10)
            with Session(customer_engine) as blocker:
                if lock_kind == "workspace":
                    blocker.scalar(select(Workspace).where(Workspace.id == wid).with_for_update())
                elif lock_kind == "mandate":
                    blocker.scalar(
                        select(Mandate).where(Mandate.workspace_id == wid).with_for_update()
                    )
                else:
                    blocker.scalar(
                        select(GoogleCustomerConnection)
                        .where(GoogleCustomerConnection.workspace_id == wid)
                        .with_for_update()
                    )
                proceed.set()
                deadline = monotonic() + 10
                with customer_engine.connect() as observer:
                    while not observer.scalar(
                        text("select cardinality(pg_blocking_pids(:pid))"), {"pid": backend[0]}
                    ):
                        assert monotonic() < deadline, "worker never reached the held row lock"
                        sleep(0.01)
                now[0] = NOW + timedelta(minutes=5, seconds=1)
                blocker.rollback()
            with pytest.raises(HTTPException, match="qualification"):
                future.result(timeout=10)
        finally:
            proceed.set()
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderReviewApproval)) == 0
        assert db.scalar(select(func.count()).select_from(ProviderReviewRecord)) == (
            1 if operation == "approve" else 0
        )


def test_approval_records_fresh_decision_time(
    customer_engine: Engine, configuration: Settings, tmp_path: Any
) -> None:
    ticks = [NOW]

    def clock() -> Any:
        ticks.append(ticks[-1] + timedelta(seconds=1))
        return ticks[-1]

    with Session(customer_engine) as db:
        wid, draft, actor, store = seeded(db, configuration, tmp_path)
        row = prepare(db, wid, draft, actor, store)
        approval = s.approve(
            db, wid, row.id, row.review_digest, row.plan_digest, actor, store, clock
        )
        from app.shopify.security import utc

        assert utc(approval.approved_at) == ticks[-1]
        assert approval.approved_at != ticks[1]
