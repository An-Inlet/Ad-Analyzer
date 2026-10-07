"""Actual PostgreSQL import lock ordering against customer closure."""

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount
from app.crm.models import CrmConnection
from app.crm.ownership import connection_for_scope
from app.imports.scope import AdvertisingImportScope, ImportScopeError, validate_advertising_scope
from app.lifecycle.quiescing import owner, quiesce
from app.workspaces.models import WorkspaceIntegration
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from tests.test_customer_exports import export_engine as export_engine
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_lifecycle import NOW, seed
from tests.test_customer_quiescing import confirmed


@pytest.mark.parametrize("provider", ["google_ads", "hubspot"])
def test_waiting_import_does_not_hold_closure_product_locks(
    export_engine: Engine, provider: str
) -> None:
    if export_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row locks")
    with Session(export_engine) as closure:
        principal, wid = seed(closure)
        integration = WorkspaceIntegration(
            workspace_id=wid,
            integration_key=provider,
            provider=provider,
            display_name=provider,
            status="active",
            configuration={},
        )
        closure.add(integration)
        closure.flush()
        iid = integration.id
        if provider == "google_ads":
            account = AdvertisingAccount(
                workspace_id=wid,
                connection_id=iid,
                platform=AdvertisingPlatform.GOOGLE_ADS,
                external_account_id="fixture",
                name="fixture",
                currency_code="USD",
            )
            closure.add(account)
            closure.flush()
            aid = account.id
        else:
            closure.add(
                CrmConnection(
                    workspace_id=wid,
                    workspace_integration_id=iid,
                    name="fixture",
                    status="active",
                    secret_manager_reference="fixture-unread",
                )
            )
            aid = 0
        closure.commit()
        request, evidence = confirmed(closure, principal, wid)
        owner(closure, principal, FakeProvider(), wid)
        closure_pid = closure.scalar(text("select pg_backend_pid()"))
        ready = Event()
        worker_pid: list[int] = []

        def worker() -> str:
            with Session(export_engine) as db:
                worker_pid.append(int(db.scalar(text("select pg_backend_pid()"))))
                ready.set()
                try:
                    if provider == "google_ads":
                        validate_advertising_scope(
                            db,
                            AdvertisingImportScope(wid, iid, aid, AdvertisingPlatform.GOOGLE_ADS),
                        )
                    else:
                        connection_for_scope(db, wid, iid)
                    return "admitted"
                except ImportScopeError:
                    return "blocked"

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(worker)
            try:
                assert ready.wait(5)
                deadline = time.monotonic() + 5
                with Session(export_engine) as observer:
                    while time.monotonic() < deadline:
                        blockers = observer.scalar(
                            text("select pg_blocking_pids(:pid)"), {"pid": worker_pid[0]}
                        )
                        if closure_pid in blockers:
                            break
                        time.sleep(0.01)
                    else:
                        pytest.fail("worker did not wait on the actual closure workspace lock")
                # If the joined import query acquired integration first, this raises
                # LockNotAvailable: closure cannot advance without a deadlock cycle.
                closure.scalar(
                    select(WorkspaceIntegration)
                    .where(WorkspaceIntegration.id == iid)
                    .with_for_update(nowait=True)
                )
                quiesce(closure, principal, FakeProvider(), wid, request, 1, evidence, NOW)
                closure.commit()
            finally:
                closure.rollback()
            assert future.result(timeout=10) == "blocked"
