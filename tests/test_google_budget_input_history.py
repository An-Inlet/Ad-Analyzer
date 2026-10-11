"""Original retained scalar corruption and actual dependency erasure, without SQL bypass."""

from pathlib import Path
from typing import Any

import pytest
from app.lifecycle.contracts import LifecycleScopeV1
from app.lifecycle.inventory import export_section
from app.planning_documents.catalog_receipt_models import CatalogReceiptRow, InputCatalogReceiptRow
from app.planning_documents.catalog_receipts import CatalogReceiptUnavailable
from sqlalchemy import Engine, delete
from sqlalchemy.orm import Session

from tests.creative_q07_fixture import planning_snapshot
from tests.google_budget_input_fixture import ready_inputs
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


@pytest.mark.parametrize("field", ["actor_id", "session_digest", "authenticated_at", "erase"])
def test_retained_original_provenance_and_export_erasure(
    customer_engine: Engine,
    configuration: Any,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    field: str,
) -> None:
    fixture, body, calls, _ = ready_inputs(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    alice, _, _ = replicas
    wid = fixture.basis.workspace_id
    root = f"/api/customer/v1/workspaces/{wid}/planning/plans"
    result = alice.post(root, headers=headers(alice), json=body)
    assert result.status_code == 201, result.text
    saved = result.json()
    scope = LifecycleScopeV1(workspace_id=wid)
    before = planning_snapshot(customer_engine), financial_counts(customer_engine), len(calls)
    with Session(customer_engine) as db:
        exported = export_section(db, scope, "planning_input_revisions")
        assert len(exported["rows"]) == 1
    if field == "erase":
        # Real supported deletion; immutable UPDATE triggers are never disabled.
        with Session(customer_engine) as db:
            db.execute(
                delete(InputCatalogReceiptRow).where(InputCatalogReceiptRow.workspace_id == wid)
            )
            db.commit()
    else:
        original_get = Session.get
        observed: list[bool] = []

        def tampered(db: Session, entity: Any, *args: Any, **kwargs: Any) -> Any:
            row = original_get(db, entity, *args, **kwargs)
            if entity is CatalogReceiptRow and row is not None:
                # Fault only the original loaded row, never current principal or persisted SQL.
                db.expunge(row)
                old = getattr(row, field)
                setattr(row, field, old + 1 if field == "authenticated_at" else "e" * len(old))
                observed.append(True)
            return row

        monkeypatch.setattr(Session, "get", tampered)
    for response in (
        alice.get(root + "/" + saved["plan_id"]),
        alice.get(root + "/requests/create/" + body["request_key"]),
        alice.post(root, headers=headers(alice), json=body),
    ):
        assert response.status_code == 409, response.text
        assert response.json()["detail"] == "The original budget owner input proof is unavailable."
    with Session(customer_engine) as db, pytest.raises(CatalogReceiptUnavailable):
        export_section(db, scope, "planning_input_revisions")
    if field != "erase":
        assert observed
        assert planning_snapshot(customer_engine) == before[0]
    assert financial_counts(customer_engine) == before[1] and len(calls) == before[2]


def test_unselected_owned_account_does_not_require_invented_historical_catalog(
    customer_engine: Engine,
    configuration: Any,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app.settings import settings
    from cryptography.fernet import Fernet
    from pydantic import SecretStr

    from tests.creative_q05_fixture import _social_account

    fixture, body, calls, _ = ready_inputs(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    monkeypatch.setattr(
        settings, "meta_token_encryption_key", SecretStr(Fernet.generate_key().decode())
    )
    aid = _social_account(customer_engine, fixture.basis.workspace_id, "meta_ads")
    body["inputs"]["account_ids"].append(aid)
    alice, _, _ = replicas
    root = f"/api/customer/v1/workspaces/{fixture.basis.workspace_id}/planning/plans"
    before_calls, before_effects = len(calls), financial_counts(customer_engine)
    result = alice.post(root, headers=headers(alice), json=body)
    assert result.status_code == 201, result.text
    saved = result.json()
    assert len(saved["inputs"]["accounts"]) == 2
    assert alice.get(root + "/" + saved["plan_id"]).status_code == 200
    with Session(customer_engine) as db:
        exported = export_section(
            db,
            LifecycleScopeV1(workspace_id=fixture.basis.workspace_id),
            "planning_input_revisions",
        )
        assert len(exported["rows"]) == 1
    assert len(calls) == before_calls and financial_counts(customer_engine) == before_effects
