"""Real SQL ownership + injected Meta wire, on disposable SQLite/PostgreSQL."""

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from app.automation.models import PlatformAutomationControl
from app.campaign_performance.selected_contracts import (
    CustomerEventSelectionV1,
    SelectedCaptureRequestV1,
    selection_digest,
)
from app.campaign_performance.selected_export import export_selected
from app.campaign_performance.selected_models import SelectedCaptureRow, SelectedFactRow
from app.campaign_performance.selected_storage import store_selection
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerSession, CustomerUser
from app.meta.models import MetaConnection
from app.meta.security import Vault
from app.meta.selected_acquisition import MetaSelectedAcquisitionUnavailable, acquire_selected
from app.meta.selected_profile import EVENT, PRODUCER, query_profile_digest, settings
from app.planning_documents.read_context import snapshot
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_meta_connection import configuration as configuration
from tests.test_meta_selected_count import raw
from tests.test_selected_storage import enforce_sqlite_fk as enforce_sqlite_fk
from tests.test_selected_storage import ready


def prepared(engine: Engine, config: Settings, monkeypatch: pytest.MonkeyPatch) -> Any:
    with Session(engine) as db:
        source, choice, old = ready(db, config, monkeypatch)
        selection = CustomerEventSelectionV1.model_validate(
            choice.model_copy(
                update={
                    "native_event_id": EVENT,
                    "api_version": "v26.0",
                    "query_profile_digest": query_profile_digest(),
                }
            )
        )
        now = datetime.now(UTC)
        req = SelectedCaptureRequestV1.model_validate(
            old.request.model_copy(
                update={
                    "schema_version": "inlet.selected-capture-request.v2",
                    "settings": settings(),
                    "selection": selection,
                    "selection_digest": selection_digest(selection),
                    "started_at": now,
                    "producer_contract": PRODUCER,
                    "query_profile_digest": query_profile_digest(),
                    "attribution": settings().effective,
                }
            )
        )
        source.encrypted_credentials = Vault(config).seal(
            source.workspace_id,
            source.external_account_id,
            {
                "access_token": "offline-selected-token",
                "expires_at": (now + timedelta(hours=1)).isoformat(),
            },
        )
        store_selection(db, selection, None, None)
        db.commit()
        user = db.get(CustomerUser, selection.confirmed_by_customer_id)
        assert user
        session = db.scalar(select(CustomerSession).where(CustomerSession.user_id == user.id))
        assert session
        principal = snapshot(CustomerPrincipal(user, session))
        provider = FakeProvider()
        provider.issuer = user.issuer
        return req, principal, provider, old.facts[0].native_campaign_id


@pytest.mark.parametrize(
    "attack",
    [
        "none",
        "session",
        "grant",
        "generation",
        "selection",
        "sync",
        "foreign_account",
        "bad_final_page",
        "final_authority",
    ],
)
def test_owned_atomic_collection_and_invalidations(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch, attack: str
) -> None:
    req, principal, provider, native = prepared(customer_engine, configuration, monkeypatch)
    if attack == "final_authority":
        from app.planning_documents.read_context import PlanningReadContexts
        from fastapi import HTTPException

        actual = PlanningReadContexts.authorize
        checks: list[int] = []

        def final_failure(self: Any, db: Session, wid: int, actor: str) -> None:
            actual(self, db, wid, actor)
            if db.scalar(select(func.count()).select_from(SelectedCaptureRow)):
                checks.append(1)
                # Body authorization succeeds; only the write-context exit fails.
                if len(checks) == 3:
                    raise HTTPException(401, "offline final authority failure")

        monkeypatch.setattr(PlanningReadContexts, "authorize", final_failure)
    calls = []

    def handler(wire: httpx.Request) -> httpx.Response:
        calls.append(wire.url.path)
        scope = req.aggregate.scope
        # Separate commits also prove SQL ownership locks are not held during IO.
        if len(calls) == 2 and attack not in {
            "none",
            "foreign_account",
            "bad_final_page",
            "final_authority",
        }:
            with Session(customer_engine) as db:
                if attack == "session":
                    session = db.get(CustomerSession, principal.session.digest)
                    assert session
                    session.revoked_at = int(datetime.now(UTC).timestamp())
                elif attack == "sync":
                    db.add(
                        PlatformAutomationControl(
                            key="all_data_syncs", enabled=False, updated_by="offline-test"
                        )
                    )
                elif attack == "selection":
                    from app.campaign_performance.selected_models import CurrentEventSelectionRow
                    from sqlalchemy import delete

                    db.execute(delete(CurrentEventSelectionRow))
                else:
                    source = db.get(MetaConnection, int(scope.source_connection_ref))
                    assert source
                    if attack == "generation":
                        source.generation += 1
                    else:
                        source.encrypted_credentials = Vault(configuration).seal(
                            scope.workspace_id,
                            scope.native_account_id,
                            {
                                "access_token": "offline-replacement",
                                "expires_at": (req.started_at + timedelta(hours=1)).isoformat(),
                            },
                        )
                db.commit()
        if not wire.url.path.endswith("/insights"):
            return httpx.Response(
                200,
                json={
                    "account_id": scope.native_account_id,
                    "currency": scope.currency,
                    "timezone_name": scope.time_zone,
                },
            )
        if wire.url.params.get("after"):
            return httpx.Response(
                200, content=b'{"data":null}' if attack == "bad_final_page" else raw([])
            )
        item = dict(
            account_id="999" if attack == "foreign_account" else scope.native_account_id,
            account_currency=scope.currency,
            campaign_id=native,
            date_start=req.requested_ends_on.isoformat(),
            date_stop=req.requested_ends_on.isoformat(),
            actions=[{"action_type": EVENT, "value": "0"}],
        )
        return httpx.Response(
            200,
            content=raw(
                [item], paging={"next": "https://ignored.invalid", "cursors": {"after": "A"}}
            ),
        )

    def acquire() -> Any:
        return acquire_selected(
            req,
            sessions=lambda: Session(customer_engine),
            principal=principal,
            provider=provider,
            configuration=configuration,
            transport=httpx.MockTransport(handler),
            clock=lambda: req.started_at,
        )

    if attack != "none":
        with pytest.raises(MetaSelectedAcquisitionUnavailable):
            acquire()
        if attack == "final_authority":
            assert checks == [1, 1, 1] and len(calls) == 4
        with Session(customer_engine) as db:
            assert db.scalar(select(func.count()).select_from(SelectedCaptureRow)) == 0
            assert db.scalar(select(func.count()).select_from(SelectedFactRow)) == 0
        return
    capture = acquire()
    assert len(calls) == 4 and capture.page_count == 2
    assert capture.facts[0].selected_conversions.value == 0
    assert capture.facts[0].selected_value_micros.presence == "unsupported"
    assert acquire() == capture and len(calls) == 4
    with Session(customer_engine) as db:
        for model in (SelectedCaptureRow, SelectedFactRow):
            saved = db.scalar(select(model))
            assert saved
            document = export_selected(
                db,
                model.__tablename__,
                {c.name: getattr(saved, c.name) for c in saved.__table__.columns},
            )
            assert document["currentness"] == "historical_as_observed"
        assert db.scalar(select(func.count()).select_from(SelectedCaptureRow)) == 1
