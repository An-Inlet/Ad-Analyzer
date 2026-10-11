"""Historical proof checks, separate from current-use and archive authority."""

from datetime import timedelta
from typing import Any

import pytest
from app.ads.models import Campaign
from app.campaign_performance.models import CurrentPerformance
from app.campaign_performance.selected_models import SelectedFactRow
from app.planning_documents.models import PlanDependencyRow
from app.planning_documents.selected_plan_history import (
    validate_selected_historical_dependencies,
    validate_selected_historical_pin,
)
from app.planning_documents.selected_plan_reader import OwnedSelectedPlanContext
from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_google_customer_connections import configured as configured
from tests.test_selected_customer_api import CustomerFixture
from tests.test_selected_customer_api import customer as customer
from tests.test_selected_plan_proof import none_document
from tests.test_selected_plan_reader import ready


def dependencies() -> list[PlanDependencyRow]:
    document = none_document()
    common = dict(
        workspace_id=document.inputs.workspace_id,
        plan_id=document.inputs.plan_id,
        version=document.version,
    )
    rows = []
    for ref in document.evidence:
        rows.append(
            PlanDependencyRow(
                **common,
                evidence_key=ref.key,
                account_id=ref.account.account_id if ref.account else None,
                connection_id=ref.account.connection_id if ref.account else None,
                store_id=document.inputs.goal.definition.store_id
                if ref.kind == "shopify_measurement"
                else None,
                kind=ref.kind,
                source_binding_digest=ref.source_binding_digest,
                document_digest=ref.document_digest,
                source_revision=ref.source_revision,
                observed_at=ref.observed_at,
                expires_at=ref.expires_at,
                privacy_revision=ref.privacy_revision,
            )
        )
    assert document.selected_reporting_proof
    for account in document.selected_reporting_proof.accounts:
        fence = account.source_fence
        rows.append(
            PlanDependencyRow(
                **common,
                evidence_key=f"local:reporting:{fence.account.account_id}",
                account_id=fence.account.account_id,
                connection_id=fence.account.connection_id,
                store_id=None,
                kind="local_reporting_v3",
                source_binding_digest=fence.source_binding_digest,
                document_digest=account.state_digest(),
                source_revision=fence.source_revision,
                observed_at=document.generated_at,
                expires_at=document.valid_until,
                privacy_revision=fence.privacy_revision,
            )
        )
    rows.append(
        PlanDependencyRow(
            **common,
            evidence_key=f"local:commerce:{document.inputs.goal.definition.store_id}",
            account_id=None,
            connection_id=None,
            store_id=document.inputs.goal.definition.store_id,
            kind="local_commerce_v1",
            source_binding_digest="1" * 64,
            document_digest="2" * 64,
            source_revision="1",
            observed_at=document.generated_at,
            expires_at=document.valid_until,
            privacy_revision=document.evidence[0].privacy_revision,
        )
    )
    return rows


def test_exact_no_selected_history_has_no_capture_fallback() -> None:
    assert validate_selected_historical_dependencies(none_document(), dependencies()) == ()


@pytest.mark.parametrize("index", [0, -2, -1])
@pytest.mark.parametrize(
    "field,value",
    [
        ("workspace_id", 999),
        ("plan_id", "f" * 32),
        ("version", 999),
        ("privacy_revision", 999),
        ("kind", "local_reporting_v2"),
        ("connection_id", 999),
        ("evidence_key", "extra"),
    ],
)
def test_scope_and_dependency_kind_changes_reject(index: int, field: str, value: Any) -> None:
    rows = dependencies()
    setattr(rows[index], field, value)
    with pytest.raises(ValueError):
        validate_selected_historical_dependencies(none_document(), rows)


@pytest.mark.parametrize("mode", ["missing", "duplicate", "extra", "early", "expiry", "hash"])
def test_complete_set_time_and_selected_digest(mode: str) -> None:
    document, rows = none_document(), dependencies()
    if mode == "missing":
        rows.pop()
    elif mode == "duplicate":
        rows.append(rows[0])
    elif mode == "extra":
        extra = dependencies()[0]
        extra.evidence_key = "extra"
        rows.append(extra)
    elif mode == "early":
        rows[-2].observed_at = document.generated_at - timedelta(seconds=1)
    elif mode == "expiry":
        rows[-1].expires_at = document.valid_until + timedelta(seconds=1)
    else:
        rows[-2].document_digest = "f" * 64
    with pytest.raises(ValueError):
        validate_selected_historical_dependencies(document, rows)


@pytest.mark.parametrize("mode", ["unchanged", "current_advanced", "missing_graph", "mapping"])
def test_actual_retained_capture_is_independent_of_current_head(
    customer: CustomerFixture, mode: str
) -> None:
    contexts, kwargs, _, _ = ready(customer)
    with contexts.open() as db, OwnedSelectedPlanContext(db, **kwargs) as reader:
        pin = reader.pin
    with Session(customer.engine) as db:
        if mode == "current_advanced":
            # Aggregate pointer removal leaves the retained completion graph intact.
            db.execute(
                delete(CurrentPerformance).where(CurrentPerformance.account_id == customer.aid)
            )
        elif mode == "missing_graph":
            db.execute(delete(SelectedFactRow).where(SelectedFactRow.capture_id == pin.capture_id))
        elif mode == "mapping":
            db.execute(
                update(Campaign)
                .where(Campaign.account_id == customer.aid)
                .values(external_campaign_id="999")
            )
        db.commit()
    with Session(customer.engine) as db:
        if mode in {"missing_graph", "mapping"}:
            with pytest.raises(ValueError):
                validate_selected_historical_pin(db, pin)
        else:
            validate_selected_historical_pin(db, pin)
            with pytest.raises(ValueError):
                validate_selected_historical_pin(
                    db, pin.model_copy(update={"capture_digest": "f" * 64})
                )
