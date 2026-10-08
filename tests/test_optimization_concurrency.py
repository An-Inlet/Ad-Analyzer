from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from app.publication import optimization as o
from app.publication.execution_models import ProviderExecutionAttempt, ProviderExposureReservation
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_durable_optimization import ready
from tests.test_shopify_sales import configuration as configuration

pytestmark = [pytest.mark.retained_execution, pytest.mark.usefixtures("retained_execution_engine")]


def test_concurrent_workers_claim_one_native_owner_and_original_attempt(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
    if customer_engine.dialect.name != "postgresql":
        pytest.skip("real PostgreSQL row locks required")
    with Session(customer_engine) as db:
        wid, actor, binding, scope, target, action, runtime, _ = ready(
            db, configuration, tmp_path, "meta_ads"
        )
        row = o.prepare_optimization(
            db, wid, binding, scope, target, action, "a" * 64, actor, runtime, lambda: NOW
        )
        o.approve_optimization(
            db, wid, row.id, row.digest, row.plan_digest, actor, runtime, lambda: NOW
        )
        run = o.create_run(db, wid, row.id, actor, runtime, lambda: NOW)
        run_id = run.id
    barrier = Barrier(2)

    def worker():  # type: ignore[no-untyped-def]
        with Session(customer_engine) as db:
            barrier.wait(timeout=10)
            return o.claim_step(db, wid, run_id, actor, runtime, lambda: NOW)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker) for _ in range(2)]
        results = [future.result(timeout=20) for future in futures]
    assert sum(result is not None for result in results) == 1
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 1
        assert db.scalar(select(func.count()).select_from(ProviderExposureReservation)) == 1
