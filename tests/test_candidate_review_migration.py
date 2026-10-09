"""0068 empty roundtrip, atomic bridge persistence and populated downgrade refusal."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from app.optimization_candidates.review_models import CandidateReviewLink
from app.settings import Settings, settings
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import create_engine, inspect, make_url, text
from sqlalchemy.orm import Session

from tests.candidate_review_link_retained_fixture import retained_candidate_review_link
from tests.test_shopify_sales import configuration as configuration


def test_candidate_review_migration_roundtrip(
    monkeypatch: pytest.MonkeyPatch, configuration: Settings, tmp_path: Path
) -> None:
    if (
        not os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL")
        or os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") != "true"
    ):
        pytest.skip("explicit disposable PostgreSQL required")
    url = validate_disposable_url()
    schema = "inlet_candidates_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
    engine = create_engine(scoped)
    monkeypatch.setattr(settings, "database_url", scoped.render_as_string(hide_password=False))
    config = Config("alembic.ini")
    try:
        command.upgrade(config, "20261006_0068")
        command.downgrade(config, "20261006_0062")
        assert "optimization_candidate_reviews" not in inspect(engine).get_table_names()
        command.upgrade(config, "20261006_0068")
        # Populate the composed current application after the exact 0068 roundtrip.
        command.upgrade(config, "heads")
        with retained_candidate_review_link(engine, tmp_path / "review-source") as (_, value):
            with Session(engine) as db:
                assert db.get(CandidateReviewLink, value.review_id)
            with pytest.raises(RuntimeError, match="cannot be discarded"):
                command.downgrade(config, "20261006_0062")
            with Session(engine) as db:
                assert db.get(CandidateReviewLink, value.review_id)
    finally:
        engine.dispose()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
