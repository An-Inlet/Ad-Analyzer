from pathlib import Path

from app.reported_feedback.service import read_comparison_progress, request_comparison
from app.settings import Settings
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.reported_feedback_fixture import seeded
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_shopify_sales import configuration as configuration


def test_actual_receipt_admits_owned_idempotent_job(
    customer_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    with Session(customer_engine) as db:
        wid, principal, provider, runtime, intent, progress, _, server = seeded(
            db, configuration, tmp_path
        )
        again = request_comparison(db, principal, provider, wid, intent, runtime)
        assert again.id == progress.id
        assert progress.completed_observations == 0 and progress.required_observations == 4
        assert len(server.posts) == 1
        assert (
            read_comparison_progress(db, principal, provider, wid, progress.id, runtime).id
            == progress.id
        )
