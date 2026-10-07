"""0058 empty roundtrip and populated downgrade refusal in disposable PostgreSQL."""

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from app.publication import replacement as r
from app.publication.execution_models import ProviderExecutionReview, ProviderReservationReplacement
from app.publication.replacement_contracts import RepeatOptimizationReview
from app.settings import Settings, settings
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, create_engine, inspect, make_url, select, text
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from tests.optimization_origin_historical_schema import legacy_origin as legacy_origin
from tests.test_commerce_measurement import NOW
from tests.test_repeat_optimization import prepared
from tests.test_shopify_sales import configuration as configuration
from tests.test_social_configuration_migration import HistoricalFixtureSession


class ReplacementHistoricalSession(HistoricalFixtureSession):
    """Expose only the absent initial-preview discriminator's historical meaning."""

    def get(self, *args: Any, **kwargs: Any) -> Any:
        row = super().get(*args, **kwargs)
        if isinstance(row, ProviderExecutionReview):
            columns = {c["name"] for c in inspect(self.connection()).get_columns(row.__tablename__)}
            assert (
                not {"initial_preview_provenance_required", "initial_preview_origin_id"} & columns
            )
            # No SQL writes or guard stubs: the real forward guard still verifies
            # the owned review, while this pre0076 schema cannot mark its origin.
            set_committed_value(row, "initial_preview_provenance_required", False)
            set_committed_value(row, "initial_preview_origin_id", None)
        return row


def test_replacement_migration_preserves_populated_obligations(
    monkeypatch: pytest.MonkeyPatch,
    configuration: Settings,
    tmp_path: Path,
    legacy_origin: Callable[[Engine], None],
) -> None:
    if (
        not os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL")
        or os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") != "true"
    ):
        pytest.skip("explicit disposable PostgreSQL required")
    url = validate_disposable_url()
    schema = "inlet_replace_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
    engine = create_engine(scoped)
    monkeypatch.setattr(settings, "database_url", scoped.render_as_string(hide_password=False))
    config = Config("alembic.ini")
    try:
        command.upgrade(config, "20261006_0058")
        command.downgrade(config, "20261006_0057")
        assert "provider_reservation_replacements" not in inspect(engine).get_table_names()
        command.upgrade(config, "20261006_0058")
        from tests.candidate_historical_schema import without_candidates

        without_candidates(monkeypatch, engine)
        legacy_origin(engine)
        # Reflect only historical review columns and assert no newer authority
        # marker is set. Never create then discard protected 0066 completion data.
        with ReplacementHistoricalSession(engine) as db:
            wid, actor, old, run, row, runtime, _ = prepared(db, configuration, tmp_path)
            r.transfer(
                db,
                wid,
                run,
                RepeatOptimizationReview.model_validate(row.document),
                actor,
                runtime,
                lambda: NOW,
            )
            replacement_ids = set(db.scalars(select(ProviderReservationReplacement.id)))
            assert replacement_ids
        with Session(engine) as db:
            assert set(db.scalars(select(ProviderReservationReplacement.id))) == replacement_ids
        with pytest.raises(RuntimeError, match="cannot be discarded"):
            command.downgrade(config, "20261006_0057")
        with Session(engine) as db:
            assert set(db.scalars(select(ProviderReservationReplacement.id))) == replacement_ids
    finally:
        engine.dispose()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
