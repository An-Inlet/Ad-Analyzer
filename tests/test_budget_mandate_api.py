"""No prior production mandate; actual APIs and configured owned GET-only runtime."""

from pathlib import Path
from typing import Any

import pytest
from app.initial_planning.budget_mandate_models import BudgetMandatePreparationRow
from app.initial_planning.planning_consent_models import PlanningConsentRow
from app.publication.customer_optimization_contracts import get_customer_optimization_runtime
from app.publication.customer_runtime import get_customer_execution_runtime
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionConsent,
    ProviderExecutionMandate,
    ProviderExposureReservation,
)
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.budget_mandate_fixture import first_customer
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def test_first_customer_mandate_and_preview(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> None:
    alice, root, body, policy, requests, control, wid, server = first_customer(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
    )
    assert get_customer_execution_runtime() is None and get_customer_optimization_runtime() is None
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderExecutionMandate)) == 0
    prepared = alice.post(root + "/budget-mandates", json=body, headers=headers(alice))
    assert prepared.status_code == 201, prepared.text
    value = prepared.json()
    consent = {
        "selection": body["intent"]["selection"],
        "expected_revision": value["revision"],
        "policy_digest": value["policy_digest"],
        "preparation_digest": value["preparation_digest"],
    }
    previous = None
    for _ in range(2):
        result = alice.post(
            root + "/budget-mandates/" + value["mandate_id"] + "/consent",
            json=consent,
            headers=headers(alice),
        )
        assert result.status_code == 200 and result.json()["state"] == "confirmed", result.text
        with Session(customer_engine) as db:
            confirmation = db.get(PlanningConsentRow, (value["mandate_id"], value["revision"]))
            assert confirmation
            snapshot = (confirmation.digest, confirmation.actor, confirmation.confirmed_at)
            if previous is not None:
                assert snapshot == previous
            previous = snapshot
    selection = body["intent"]["selection"]
    preview = alice.post(
        root + "/previews",
        headers=headers(alice),
        json={
            "calibration_id": selection["calibration_id"],
            "observation_id": selection["observation_id"],
            "choice": {"option_id": selection["native_option_id"]},
            "mandate_id": value["mandate_id"],
            "mandate_revision": value["revision"],
        },
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["schema_version"] == "inlet.initial-efficiency-preview.v2"
    assert not preview.json()["spending_authorized"]
    reread = alice.get(root + "/previews/" + preview.json()["id"])
    assert reread.status_code == 200, reread.text
    refreshed = alice.post(
        root + "/native-options",
        headers=headers(alice),
        json={
            "calibration_id": selection["calibration_id"],
            "observation_id": selection["observation_id"],
        },
    )
    assert refreshed.status_code == 200, refreshed.text
    assert [m["id"] for m in refreshed.json()["mandates"]] == [value["mandate_id"]]
    with Session(customer_engine) as db:
        for model, count in (
            (ProviderExecutionMandate, 1),
            (ProviderExecutionConsent, 0),
            (PlanningConsentRow, 1),
            (BudgetMandatePreparationRow, 1),
            (ProviderExecutionAttempt, 0),
            (ProviderExposureReservation, 0),
        ):
            assert db.scalar(select(func.count()).select_from(model)) == count
    with Session(customer_engine) as db:
        assert db.scalar(select(ProviderExecutionMandate.state)) == "draft"
    assert requests and not server.posts


@pytest.mark.parametrize(
    "change", ["policy", "profile", "session", "scope", "cap", "technical", "rollback"]
)
def test_conditional_consent_fences_and_atomic_rollback(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    change: str,
) -> None:
    from app.settings import settings
    from sqlalchemy import event

    alice, root, body, policy, requests, control, wid, server = first_customer(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
    )
    if change == "cap":
        body["intent"]["total_cap_micros"] += 10000
    elif change == "technical":
        body["intent"]["freshness_seconds"] = 30
    elif change == "rollback":

        def revoke_after_insert(*args: Any) -> None:
            replicas[2].revoked.add("budget-first")

        event.listen(BudgetMandatePreparationRow, "after_insert", revoke_after_insert)
    try:
        result = alice.post(root + "/budget-mandates", json=body, headers=headers(alice))
    finally:
        if change == "rollback":
            event.remove(BudgetMandatePreparationRow, "after_insert", revoke_after_insert)
    if change in {"cap", "technical", "rollback"}:
        assert result.status_code in {401, 409, 422}, result.text
        with Session(customer_engine) as db:
            for model in (ProviderExecutionMandate, BudgetMandatePreparationRow):
                assert db.scalar(select(func.count()).select_from(model)) == 0
        return
    assert result.status_code == 201, result.text
    value = result.json()
    if change == "policy":
        changed = policy.model_copy(update={"revision": 2})
        path = tmp_path / "new-policy.json"
        path.write_text(changed.model_dump_json())
        monkeypatch.setattr(settings, "budget_mandate_policy_path", str(path))
        monkeypatch.setattr(settings, "budget_mandate_policy_digest", changed.digest())
    elif change == "profile":
        monkeypatch.setattr(settings, "budget_mandate_policy_path", None)
        monkeypatch.setattr(settings, "budget_mandate_policy_digest", None)
    elif change == "session":
        import time

        from app.customers.access import SESSION_COOKIE, digest
        from app.customers.models import CustomerSession

        session_key = digest(alice.cookies[SESSION_COOKIE])

        def revoke_during_http() -> None:
            with Session(customer_engine) as concurrent:
                row = concurrent.get(CustomerSession, session_key)
                assert row is not None
                row.revoked_at = int(time.time())
                concurrent.commit()

        control["callback"] = revoke_during_http
    elif change == "scope":
        server.extra_child = True
    result = alice.post(
        root + "/budget-mandates/" + value["mandate_id"] + "/consent",
        headers=headers(alice),
        json={
            "selection": body["intent"]["selection"],
            "expected_revision": 1,
            "policy_digest": value["policy_digest"],
            "preparation_digest": value["preparation_digest"],
        },
    )
    assert result.status_code in {401, 403, 409}, result.text
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderExecutionConsent)) == 0
