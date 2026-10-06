"""Only generated schemas on explicitly disposable PostgreSQL are modified."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from app.publication.execution_authorization import owner_authorizer
from app.publication.execution_models import ProviderExecutionRun
from app.publication.social_review_contracts import MetaNoDSAAnswer, SocialRequirements
from app.publication.social_review_models import SocialConfigurationReview
from app.publication.social_review_service import confirm, prepare, selection
from app.settings import Settings, settings
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import create_engine, insert, inspect, make_url, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_shopify_sales import configuration as configuration
from tests.test_social_customer_producer import fixture


def test_populated_no_dsa_review_roundtrip(
    monkeypatch: pytest.MonkeyPatch, configuration: Settings, tmp_path: Path
) -> None:
    if not os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL") or (
        os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") != "true"
    ):
        pytest.skip("explicit disposable PostgreSQL required")
    url = validate_disposable_url()
    schema = "inlet_social_config_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
    engine = create_engine(scoped)
    monkeypatch.setattr(settings, "database_url", scoped.render_as_string(hide_password=False))
    config = Config("alembic.ini")
    try:
        command.upgrade(config, "20261006_0057")
        with Session(engine) as db:
            _, account, catalog, producer, actor, store, _, _ = fixture(
                db, configuration, tmp_path, "meta_ads", None
            )
            db.commit()
            profile = next(iter(producer.profiles.values())).model_copy(
                update={"dsa_required": False}
            )
            option = catalog.options[0].model_copy(update={"profile_digest": profile.digest()})
            catalog = catalog.model_copy(update={"options": [option]})
        command.upgrade(config, "20261006_0059")
        with Session(engine) as db:
            document = selection(
                db,
                account.workspace_id,
                actor,
                account,
                catalog,
                option.identifier(catalog.request),
                profile,
                SocialRequirements(
                    profile_digest=profile.digest(),
                    requirements_digest="a" * 64,
                    wording_version="test-v1",
                    verified=True,
                    dsa_required=False,
                    wording="Offline Test: Review This No-DSA Profile And Its Exact Media.",
                ),
                MetaNoDSAAnswer(special_category_answer="none_applicable"),
                None,
                "contract_test",
                store,
                lambda: NOW,
                owner_authorizer,
            )
            row = prepare(db, account.workspace_id, actor, document, lambda: NOW, owner_authorizer)
            identifier = row.id
            confirm(
                db,
                account.workspace_id,
                row.id,
                row.digest,
                actor,
                document,
                lambda: NOW,
                owner_authorizer,
            )
            db.commit()
            mapping = {column.name: getattr(row, column.name) for column in row.__table__.columns}
            with pytest.raises(IntegrityError), db.begin_nested():
                db.execute(
                    insert(SocialConfigurationReview).values(
                        **{
                            **mapping,
                            "id": uuid4().hex,
                            "workspace_id": account.workspace_id + 9999,
                        }
                    )
                )
        command.downgrade(config, "20261006_0057")
        assert "customer_social_configuration_reviews" not in inspect(engine).get_table_names()
        with Session(engine) as db:
            assert db.query(ProviderExecutionRun).count() == 1
        command.upgrade(config, "20261006_0059")
        with Session(engine) as db:
            assert db.get(SocialConfigurationReview, identifier) is None
            assert db.query(ProviderExecutionRun).count() == 1
    finally:
        engine.dispose()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
