"""Install immutable synthetic pages independently of the customer's proposed amount."""

import json

import pytest
from app.lifecycle.privacy import workspace_export_revision
from app.main import app
from app.planning_documents.google_budget_fixture_runtime import FixturePage, GoogleBudgetFixture
from app.planning_documents.google_budget_read import Query
from app.publication import customer_intents
from app.publication.contracts import fingerprint
from app.settings import settings
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.google_budget_read_fixture import Search


def install_fixture(
    engine: Engine, patch: pytest.MonkeyPatch, workspace: int, account: int, zone: str,
) -> GoogleBudgetFixture:
    with Session(engine) as db:
        scope = customer_intents.account(db, workspace, account)
        privacy = workspace_export_revision(db, workspace)
    synthetic = Search(scope.external_advertiser_id, amount=5_000_000)
    synthetic.data["customer"][0]["customer"]["timeZone"] = zone
    kinds: tuple[Query, ...] = ("customer", "campaign", "campaignBudget")
    fixture = GoogleBudgetFixture(
        workspace_id=workspace, privacy_revision=privacy,
        source_binding_digest=fingerprint(
            "inlet.planning-source.v1", scope.model_dump(mode="json")
        ),
        pages=tuple(FixturePage(
            query_kind=kind, request_cursor=None,
            response_json=json.dumps(dict(results=synthetic.data[kind])),
        ) for kind in kinds),
    )
    patch.setattr(app.state, "google_budget_observation_fixture", fixture, raising=False)
    patch.setattr(settings, "customer_google_budget_observation_mode", "injected_fixture")
    return fixture
