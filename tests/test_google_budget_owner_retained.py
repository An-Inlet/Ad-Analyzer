"""Historical subset validation and actual immutable input receipt value loader."""

from pathlib import Path
from typing import Any

import pytest
from app.planning_documents import google_budget_owner_retained as retained
from app.planning_documents.catalog_receipt_models import CatalogReceiptRow, InputCatalogReceiptRow
from app.planning_documents.catalog_receipts import (
    CatalogReceiptUnavailable,
    _validated_retained_input_receipts,
)
from app.planning_documents.context import PlanInputRevision
from app.planning_documents.google_budget_owner_review import (
    compose_google_budget_owner_reviews as compose,
)
from app.planning_documents.google_budget_owner_review import (
    validate_google_budget_owner_review as active,
)
from app.planning_documents.google_budget_owner_review import (
    validate_retained_google_budget_owner_review as historical,
)
from sqlalchemy import Engine, delete
from sqlalchemy.orm import Session

from tests.creative_q07_fixture import planning_snapshot
from tests.google_budget_input_fixture import ready_inputs
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_google_budget_owner_review import ready
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("empty", [False, True])
def test_historical_subset_preserves_unselected_account_and_active_full_scope(empty: bool) -> None:
    values = ready(empty=empty)
    original = values["sources"][0]
    extra = original.account.model_copy(update={"account_id": original.account.account_id + 1})
    raw = values["inputs"].model_dump(mode="python")
    raw["accounts"] = (*raw["accounts"], extra)
    values["inputs"] = PlanInputRevision.model_validate(raw)
    values["sources"] = (original, original.model_copy(update={"account": extra}))
    actions, proof = compose(**values, first_priority=1)
    values.pop("privacy_revision")
    values["sources"] = (original,)
    historical(**values, actions=actions, proof=proof)
    with pytest.raises(ValueError, match="full source"):
        active(**values, actions=actions, proof=proof, privacy_revision=original.privacy_revision)


@pytest.mark.parametrize("case", ["missing", "extra", "duplicate", "foreign", "raw", "proof"])
def test_historical_subset_never_fabricates_source_context(case: str) -> None:
    values = ready()
    actions, proof = compose(**values, first_priority=1)
    values.pop("privacy_revision")
    source = values["sources"][0]
    if case == "missing":
        values["sources"] = ()
    elif case == "duplicate":
        values["sources"] *= 2
    elif case == "extra":
        values["sources"] += (
            source.model_copy(
                update={
                    "account": source.account.model_copy(
                        update={"account_id": source.account.account_id + 1}
                    )
                }
            ),
        )
    elif case == "foreign":
        values["sources"] = (
            source.model_copy(update={"privacy_revision": source.privacy_revision + 1}),
        )
    elif case == "raw":
        catalog = values["catalogs"][0]
        values["catalogs"] = (
            catalog.model_copy(
                update={
                    "catalog": catalog.catalog.model_copy(
                        update={
                            "native_observation": catalog.catalog.native_observation.model_copy(
                                update={"advertising_writes_enabled": 0}
                            )
                        }
                    )
                }
            ),
        )
    else:
        proof = proof.model_copy(update={"input_digest": "0" * 64})
    with pytest.raises(ValueError):
        historical(**values, actions=actions, proof=proof)


@pytest.mark.planning_boundary
@pytest.mark.parametrize(
    "case",
    [
        "normal",
        "empty",
        "unselected",
        "scalar",
        "missing",
        "dirty",
        "transaction",
        "connection",
        "nested",
        "foreign",
    ],
)
def test_actual_saved_input_loader_returns_values_and_preserves_original_graph(
    customer_engine: Engine,
    configuration: Any,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    case: str,
) -> None:
    fixture, body, calls, _ = ready_inputs(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    alice, _, _ = replicas
    wid = fixture.basis.workspace_id
    if case == "empty":
        body["inputs"]["google_daily_budget_intents"] = []
        body["inputs"]["scenario_intents"] = []
        assert not body["inputs"].get("fixed_allocations")
        assert not body["inputs"].get("exclusions")
    if case == "unselected":
        from app.settings import settings
        from cryptography.fernet import Fernet
        from pydantic import SecretStr

        from tests.creative_q05_fixture import _social_account

        monkeypatch.setattr(
            settings, "meta_token_encryption_key", SecretStr(Fernet.generate_key().decode())
        )
        body["inputs"]["account_ids"].append(_social_account(customer_engine, wid, "meta_ads"))
    result = alice.post(
        f"/api/customer/v1/workspaces/{wid}/planning/plans", headers=headers(alice), json=body
    )
    assert result.status_code == 201, result.text
    inputs = PlanInputRevision.model_validate(result.json()["inputs"])
    if case == "missing":
        with Session(customer_engine) as db:
            db.execute(
                delete(InputCatalogReceiptRow).where(InputCatalogReceiptRow.workspace_id == wid)
            )
            db.commit()
    before = planning_snapshot(customer_engine), financial_counts(customer_engine), len(calls)
    if case == "scalar":
        original_get = Session.get

        def changed(db: Session, entity: Any, *args: Any, **kwargs: Any) -> Any:
            row = original_get(db, entity, *args, **kwargs)
            if entity is CatalogReceiptRow and row is not None:
                db.expunge(row)
                row.authenticated_at += 1
            return row

        monkeypatch.setattr(Session, "get", changed)
    if case in {"transaction", "connection", "nested"}:
        original = _validated_retained_input_receipts

        def replaced(db: Session, value: PlanInputRevision) -> Any:
            result = original(db, value)
            if case == "transaction":
                db.rollback()
                db.begin()
            elif case == "connection":
                connection = db.connection()
                connection.rollback()
                connection.begin()
            else:
                db.connection().begin_nested()
            return result

        monkeypatch.setattr(retained, "_validated_retained_input_receipts", replaced)
    if case == "foreign":
        inputs = inputs.model_copy(update={"plan_id": "e" * 32})
    with Session(customer_engine) as db:
        with pytest.raises(CatalogReceiptUnavailable):
            retained.load_retained_owner_input_evidence(db, inputs)
        assert not db.in_transaction()
        db.begin()
        if case == "dirty":
            from sqlalchemy import select

            row = db.scalars(select(CatalogReceiptRow)).first()
            assert row is not None
            row.authenticated_at += 1
        if case in {"scalar", "missing", "dirty", "transaction", "connection", "nested", "foreign"}:
            with pytest.raises(CatalogReceiptUnavailable):
                retained.load_retained_owner_input_evidence(db, inputs)
        else:
            value = retained.load_retained_owner_input_evidence(db, inputs)
            assert set(type(value).model_fields) == {"catalogs", "sources"}
            assert len(value.catalogs) == len(value.sources) == (0 if case == "empty" else 1)
            assert (
                retained.RetainedOwnerInputEvidence.model_validate_json(value.model_dump_json())
                == value
            )
            if case == "unselected":
                assert len(inputs.accounts) == 2 and len(value.sources) == 1
            with pytest.raises(ValueError):
                value.__setattr__("sources", ())
        db.rollback()
    assert (
        planning_snapshot(customer_engine),
        financial_counts(customer_engine),
        len(calls),
    ) == before
