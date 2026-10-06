"""Child rows reconcile with campaign totals without adding overlapping metric grains."""

from copy import deepcopy
from datetime import date
from typing import Any

import pytest
from app.ads.enums import AdvertisingPlatform
from app.ads.models import Ad, DailyMetric
from app.imports.scope import AdvertisingImportScope
from app.meta.client import MetaClient
from app.meta.detail import DetailBatch, collect, detail_report, publish
from app.meta.security import MetaError
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_meta_connection import FakeMeta, complete, connected, insight, page
from tests.test_meta_connection import configuration as configuration

DAY = date(2026, 9, 5)


class DetailClient(FakeMeta):
    def detail_page(
        self, account_id: str, token: str, phase: str, cursor: str | None, start: date, end: date
    ) -> dict[str, Any]:
        self.requests.append((account_id, phase, cursor))
        response = self.pages.pop(0)
        if isinstance(response, Exception):
            raise response
        return dict(response)


def inventory(number: str, name: str = "Fixture ad") -> dict[str, Any]:
    return {
        "id": number,
        "account_id": "101",
        "campaign_id": "201",
        "adset_id": "301",
        "name": name,
        "status": "ACTIVE",
        "creative": {"id": "601", "name": "Supplied fixture"},
    }


def batch(config: Settings) -> DetailBatch:
    first = insight(adset_id="301", ad_id="401", spend="60")
    client = DetailClient(
        config,
        [
            page(inventory("401"), inventory("402")),
            page(insight(adset_id="301", spend="100")),
            page(first, deepcopy(first), insight(adset_id="301", ad_id="402", spend="40")),
        ],
    )
    return collect(client, "101", "fixture-token", DAY, DAY, "USD", "purchase")


def test_child_import_is_atomic_and_does_not_multiply_totals(
    customer_engine: Engine, configuration: Settings
) -> None:
    with Session(customer_engine) as db:
        connection = connected(db, configuration, event="purchase")
        complete(db, configuration, connection, metric=insight(spend="100"))
        scope = AdvertisingImportScope(
            connection.workspace_id,
            connection.workspace_integration_id or 0,
            connection.account_id,
            AdvertisingPlatform.META_ADS,
        )
        snapshot = batch(configuration)
        assert publish(db, scope, snapshot) == 3
        db.commit()
        report = detail_report(db, scope, DAY, DAY)
        assert report["spend_micros"] == 100_000_000 and report["children_reconcile"] is True
        assert report["comparison"] == {
            "campaign": 100_000_000,
            "ad_set": 100_000_000,
            "ad": 100_000_000,
        }
        assert report["historical_creative_attribution_available"] is False
        assert db.scalar(select(func.count()).select_from(DailyMetric)) == 4
        assert publish(db, scope, snapshot) == 3
        db.commit()
        assert db.scalar(select(func.count()).select_from(DailyMetric)) == 4
        ad = db.scalar(select(Ad).where(Ad.external_ad_id == "401"))
        assert ad is not None and ad.creative_external_id == "601"
        invalid = snapshot.model_copy(deep=True)
        invalid.inventory[0].name = "Must roll back"
        invalid.metrics[-1].ad_set_id = "999"
        with pytest.raises(HTTPException):
            publish(db, scope, invalid)
        db.commit()  # Nested import rollback protects caller even after catching rejection.
        db.expire_all()
        assert ad.name == "Fixture ad"
        assert detail_report(db, scope, DAY, DAY)["children_reconcile"] is True
        other = connected(db, configuration, slug="other", number="102")
        with pytest.raises(HTTPException, match="ownership mismatch"):
            publish(
                db,
                AdvertisingImportScope(
                    other.workspace_id,
                    other.workspace_integration_id or 0,
                    other.account_id,
                    AdvertisingPlatform.META_ADS,
                ),
                snapshot,
            )


def test_partial_and_repeated_pages_never_publish(configuration: Settings) -> None:
    client = DetailClient(configuration, [page(inventory("401")), MetaError("meta_throttled")])
    with pytest.raises(MetaError, match="meta_throttled"):
        collect(client, "101", "fixture-token", DAY, DAY, "USD", "purchase")
    client = DetailClient(
        configuration,
        [page(inventory("401"), cursor="repeat"), page(inventory("401"), cursor="repeat")],
    )
    with pytest.raises(MetaError, match="meta_invalid_cursor"):
        collect(client, "101", "fixture-token", DAY, DAY, "USD", "purchase")
    wrong = inventory("401")
    wrong["account_id"] = "102"
    with pytest.raises(MetaError, match="meta_account_mismatch"):
        collect(
            DetailClient(configuration, [page(wrong)]),
            "101",
            "fixture-token",
            DAY,
            DAY,
            "USD",
            "purchase",
        )


def test_read_transport_uses_exact_levels_without_breakdown(configuration: Settings) -> None:
    class Capture(MetaClient):
        def _request(
            self, path: str, params: dict[str, str], token: str | None = None
        ) -> dict[str, Any]:
            return {"path": path, "params": params}

    client = Capture(configuration)
    ads = client.detail_page("101", "fixture-token", "ads", None, DAY, DAY)
    assert ads["path"] == "act_101/ads" and "creative{id,name}" in ads["params"]["fields"]
    for phase, level in [("adset_insights", "adset"), ("ad_insights", "ad")]:
        result = client.detail_page("101", "fixture-token", phase, "page-two", DAY, DAY)
        assert result["path"] == "act_101/insights" and result["params"]["level"] == level
        assert "breakdowns" not in result["params"] and result["params"]["after"] == "page-two"


def test_populated_migration_preserves_campaign_rows_and_parent_constraints(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    if customer_engine.dialect.name != "postgresql":
        return
    from alembic import command
    from alembic.config import Config
    from app.settings import settings
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    with Session(customer_engine) as db:
        connection = connected(db, configuration, event="purchase")
        complete(db, configuration, connection, metric=insight(spend="100"))
        wid, iid, aid = (
            connection.workspace_id,
            connection.workspace_integration_id,
            connection.account_id,
        )
    with customer_engine.connect() as schema_connection:
        schema = schema_connection.scalar(text("SELECT current_schema()"))
    url = customer_engine.url.update_query_dict({"options": f"-csearch_path={schema}"})
    monkeypatch.setattr(settings, "database_url", url.render_as_string(hide_password=False))
    config = Config("alembic.ini")
    command.stamp(config, "head")
    command.downgrade(config, "20261005_0028")
    command.upgrade(config, "head")
    with Session(customer_engine) as db:
        scope = AdvertisingImportScope(wid, iid or 0, aid, AdvertisingPlatform.META_ADS)
        assert detail_report(db, scope, DAY, DAY)["spend_micros"] == 100_000_000
        publish(db, scope, batch(configuration))
        db.commit()
        metric = db.scalar(select(DailyMetric).where(DailyMetric.entity_type == "ad"))
        assert metric is not None
        # A numeric ID alone cannot reparent an ad metric to a different ad set.
        with pytest.raises(IntegrityError), db.begin_nested():
            metric.ad_set_id = 999999
            db.flush()
        assert detail_report(db, scope, DAY, DAY)["children_reconcile"] is True


def test_customer_detail_report_ownership_and_revocation(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from collections.abc import Generator

    from app.api.customer import router as auth_router
    from app.api.customer_ad_detail import router
    from app.customers.identity import get_identity_provider
    from app.customers.models import CustomerMembership
    from app.database.session import get_db
    from app.settings import settings
    from app.workspaces.models import WorkspaceIntegration
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from tests.test_customer_identity import ORIGIN, FakeProvider, login

    monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(router)

    def database() -> Generator[Session, None, None]:
        with Session(customer_engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_identity_provider] = lambda: FakeProvider()
    viewer, outsider = TestClient(app, base_url=ORIGIN), TestClient(app, base_url=ORIGIN)
    user = login(viewer, "viewer:1")
    login(outsider, "outsider:1")
    with Session(customer_engine) as db:
        connection = connected(db, configuration, event="purchase")
        complete(db, configuration, connection, metric=insight(spend="100"))
        wid, cid, iid = connection.workspace_id, connection.id, connection.workspace_integration_id
        publish(
            db,
            AdvertisingImportScope(
                wid, iid or 0, connection.account_id, AdvertisingPlatform.META_ADS
            ),
            batch(configuration),
        )
        db.add(CustomerMembership(user_id=user, workspace_id=wid, role="viewer", status="active"))
        db.commit()
    path = f"/api/customer/v1/workspaces/{wid}/meta/connections/{cid}/detail?start={DAY}&end={DAY}"
    assert outsider.get(path).status_code == 404
    response = viewer.get(path)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert response.json()["spend_micros"] == 100_000_000 and len(response.json()["ads"]) == 2
    result = response.json()
    assert result["ads"][0]["performance"] == {
        "impressions": 1000,
        "clicks": 20,
        "spend_micros": 60_000_000,
        "conversions": "3.000000",
        "conversion_value_micros": 150_120_000,
    }
    assert result["ad_sets"][0]["performance"]["spend_micros"] == 100_000_000
    assert result["comparison_is_informational"] is True
    assert result["common_coverage_and_eligibility_verified"] is False
    assert viewer.get(path + "&offset=100").json()["ads"] == []
    with Session(customer_engine) as db:
        integration = db.get(WorkspaceIntegration, iid)
        assert integration is not None
        integration.status = "revoked"
        db.commit()
    assert viewer.get(path).status_code == 404


def test_equal_account_totals_do_not_claim_parent_day_agreement(
    customer_engine: Engine,
    configuration: Settings,
) -> None:
    from datetime import timedelta

    with Session(customer_engine) as db:
        connection = connected(db, configuration, event="purchase")
        complete(db, configuration, connection, metric=insight(spend="100"))
        scope = AdvertisingImportScope(
            connection.workspace_id,
            connection.workspace_integration_id or 0,
            connection.account_id,
            AdvertisingPlatform.META_ADS,
        )
        snapshot = batch(configuration)
        snapshot.start = DAY - timedelta(days=1)
        snapshot.metrics[-1].metric_date = snapshot.start
        assert publish(db, scope, snapshot) == 3  # Differences are valid evidence, not rejection.
        report = detail_report(db, scope, snapshot.start, DAY)
        assert set(report["comparison"].values()) == {100_000_000}
        assert report["children_reconcile"] is False
        assert report["spend_micros"] == 100_000_000
