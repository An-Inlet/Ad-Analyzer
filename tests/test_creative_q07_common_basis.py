"""Actual private V5 currency boundary on the unchanged Q05 Common Basis."""

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from app.settings import Settings
from sqlalchemy import Engine

from tests.creative_q05_fixture import prepare_creative_q05_basis
from tests.creative_q07_fixture import assert_owned_eur_selector, planning_snapshot
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def test_actual_v5_q07_owned_currency_rejected(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fixture = prepare_creative_q05_basis(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        tmp_path / "media",
        meta_currency="EUR",
    )
    alice, _, _ = replicas
    assert_owned_eur_selector(fixture)
    root = f"/api/customer/v1/workspaces/{fixture.creative.basis.workspace_id}/planning/plans"
    baseline = planning_snapshot(customer_engine)
    effects = financial_counts(customer_engine)
    for kind in ("scenario", "fixed", "zero"):
        body = deepcopy(fixture.body)
        body["request_key"] = "q07-eur-" + kind
        if kind != "scenario":
            body["inputs"]["scenario_intents"] = []
            body["inputs"]["fixed_allocations"] = [
                dict(
                    target=fixture.selectors[1], amount_micros=0 if kind == "zero" else 300_000_000
                )
            ]
        result = alice.post(root, headers=headers(alice), json=body)
        assert result.status_code == 422, f"owned EUR allocation save status={result.status_code}"
        assert (
            result.json()["detail"] == "Planning allocations must use the confirmed goal currency."
        )
        assert planning_snapshot(customer_engine) == baseline
        assert financial_counts(customer_engine) == effects == (0,) * 6

    # The foreign-currency account can still be inspected or explicitly excluded.
    allowed = deepcopy(fixture.body)
    allowed["request_key"] = "q07-eur-unallocated"
    allowed["inputs"]["scenario_intents"] = []
    allowed["inputs"]["fixed_allocations"] = []
    created = alice.post(root, headers=headers(alice), json=allowed)
    assert created.status_code == 201, created.text
    url = root + "/" + created.json()["plan_id"]
    replay = alice.post(root, headers=headers(alice), json=allowed)
    assert replay.status_code == 201 and replay.json() == created.json()
    baseline = planning_snapshot(customer_engine)
    broken = deepcopy(fixture.body)
    broken.update(request_key="q07-eur-edit", expected_input_revision=1, expected_version=0)
    rejected = alice.post(url + "/inputs", headers=headers(alice), json=broken)
    assert rejected.status_code == 422
    assert rejected.json()["detail"] == "Planning allocations must use the confirmed goal currency."
    assert planning_snapshot(customer_engine) == baseline
    stale = deepcopy(broken)
    stale["request_key"] = "q07-eur-stale"
    stale["inputs"]["scenario_intents"][0]["allocations"][1]["target"]["selection_key"] = "0" * 64
    rejected = alice.post(url + "/inputs", headers=headers(alice), json=stale)
    assert rejected.status_code == 409
    assert planning_snapshot(customer_engine) == baseline
    excluded = deepcopy(allowed)
    excluded.update(request_key="q07-eur-exclude", expected_input_revision=1, expected_version=0)
    excluded["inputs"]["exclusions"] = [fixture.selectors[1]]
    accepted = alice.post(url + "/inputs", headers=headers(alice), json=excluded)
    assert accepted.status_code == 200, accepted.text
    assert financial_counts(customer_engine) == effects


def test_prefixed_admitted_eur_input_cannot_generate(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app.planning_documents import input_resolution

    fixture = prepare_creative_q05_basis(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        tmp_path / "media",
        meta_currency="EUR",
    )
    alice, _, _ = replicas
    root = f"/api/customer/v1/workspaces/{fixture.creative.basis.workspace_id}/planning/plans"
    # Explicit historical pre-fix admission emulation: only the new input check is
    # disabled for this one real save. No positive document/proof is manufactured.
    with monkeypatch.context() as historical:
        historical.setattr(input_resolution, "check_allocations", lambda inputs, catalogs: None)
        created = alice.post(root, headers=headers(alice), json=fixture.body)
    assert created.status_code == 201, created.text
    baseline = planning_snapshot(customer_engine)
    effects = financial_counts(customer_engine)
    result = alice.post(
        root + "/" + created.json()["plan_id"] + "/generate",
        headers=headers(alice),
        json=dict(expected_input_revision=1, expected_version=0, request_key="q07-legacy-generate"),
    )
    assert result.status_code == 422, result.text
    assert result.json()["detail"] == "Planning allocations must use the confirmed goal currency."
    assert planning_snapshot(customer_engine) == baseline
    assert financial_counts(customer_engine) == effects == (0,) * 6


def test_actual_v5_q07_ceiling_requires_confirmed_goal_revision(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import json

    from app.planning_documents.documents import PlanVersion

    fixture = prepare_creative_q05_basis(
        customer_engine, configuration, replicas, monkeypatch, tmp_path / "media"
    )
    alice, _, _ = replicas
    workspace = f"/api/customer/v1/workspaces/{fixture.creative.basis.workspace_id}"
    plans = workspace + "/planning/plans"
    goal = workspace + "/goals/" + fixture.body["inputs"]["goal_id"]
    baseline = planning_snapshot(customer_engine)
    for kind in ("over", "negative", "currency_field", "ceiling_field", "aggression_field"):
        invalid = deepcopy(fixture.body)
        invalid["request_key"] = "q07-invalid-" + kind
        allocation = invalid["inputs"]["scenario_intents"][0]["allocations"][1]
        if kind == "over":
            allocation["amount_micros"] = 400_000_000
        elif kind == "negative":
            allocation["amount_micros"] = -1
        elif kind == "currency_field":
            allocation["currency"] = "EUR"
        elif kind == "ceiling_field":
            invalid["inputs"]["total_ceiling_micros"] = 1_100_000_000
        else:
            invalid["inputs"]["aggressiveness"] = "assertive"
        result = alice.post(plans, headers=headers(alice), json=invalid)
        assert result.status_code == 422, (kind, result.text)
        assert planning_snapshot(customer_engine) == baseline

    def revise(*, budget: int, aggression: str) -> int:
        current = alice.get(goal)
        assert current.status_code == 200
        definition = deepcopy(current.json()["definition"])
        definition.update(budget_micros=budget, aggressiveness=aggression)
        result = alice.put(
            goal,
            headers=headers(alice),
            json=dict(
                expected_revision=current.json()["revision"],
                definition=definition,
            ),
        )
        assert result.status_code == 200, result.text
        return int(result.json()["revision"])

    def confirm(revision: int) -> None:
        preview = alice.post(
            goal + "/preview", headers=headers(alice), json=dict(expected_revision=revision)
        )
        assert preview.status_code == 200, preview.text
        result = alice.post(
            goal + "/confirm",
            headers=headers(alice),
            json=dict(
                expected_revision=revision,
                preview_id=preview.json()["preview_id"],
                idempotency_key=f"q07-confirm-{revision}",
            ),
        )
        assert result.status_code == 200 and result.json()["assessment"] == "confirmed", result.text

    assertive = revise(budget=1_000_000_000, aggression="assertive")
    confirm(assertive)
    body = deepcopy(fixture.body)
    body["inputs"]["goal_revision"] = assertive
    body["request_key"] = "q07-assertive-create"
    over = deepcopy(body)
    over["request_key"] = "q07-assertive-over"
    over["inputs"]["scenario_intents"][0]["allocations"][1]["amount_micros"] = 400_000_000
    rejected = alice.post(plans, headers=headers(alice), json=over)
    assert rejected.status_code == 422, rejected.text
    assert planning_snapshot(customer_engine) == baseline
    created = alice.post(plans, headers=headers(alice), json=body)
    assert created.status_code == 201, created.text
    url = plans + "/" + created.json()["plan_id"]

    def generate(input_revision: int, version: int) -> dict[str, Any]:
        intent = dict(
            expected_input_revision=input_revision,
            expected_version=version,
            request_key=f"q07-generate-{input_revision}",
        )
        result = alice.post(url + "/generate", headers=headers(alice), json=intent)
        assert result.status_code == 200, result.text
        calls = len(fixture.native_calls)
        replay = alice.post(url + "/generate", headers=headers(alice), json=intent)
        assert replay.status_code == 200 and replay.json() == result.json()
        assert len(fixture.native_calls) == calls
        return dict(result.json()["document"])

    first = generate(1, 0)
    assert first["inputs"]["total_ceiling_micros"] == 1_000_000_000
    assert first["inputs"]["aggressiveness"] == "assertive"
    first_digest = PlanVersion.model_validate(first).digest()
    raised = revise(budget=1_100_000_000, aggression="assertive")
    edited = deepcopy(over)
    edited.update(request_key="q07-raised-edit", expected_input_revision=1, expected_version=1)
    edited["inputs"]["goal_revision"] = raised
    baseline = planning_snapshot(customer_engine)
    for revision in (assertive, raised):
        unconfirmed = deepcopy(edited)
        unconfirmed["request_key"] = f"q07-unconfirmed-{revision}"
        unconfirmed["inputs"]["goal_revision"] = revision
        denied = alice.post(url + "/inputs", headers=headers(alice), json=unconfirmed)
        assert denied.status_code == 409, denied.text
        assert denied.json()["detail"] == (
            "goal revision changed"
            if revision == assertive
            else "confirm the current goal before planning"
        )
        assert planning_snapshot(customer_engine) == baseline
    confirm(raised)
    # Both independent scenarios must reconcile to the newly confirmed ceiling.
    edited["inputs"]["scenario_intents"][1]["unallocated_micros"] = 200_000_000
    accepted = alice.post(url + "/inputs", headers=headers(alice), json=edited)
    assert accepted.status_code == 200, accepted.text
    stale = deepcopy(edited)
    stale["request_key"] = "q07-stale-input-cas"
    baseline = planning_snapshot(customer_engine)
    denied = alice.post(url + "/inputs", headers=headers(alice), json=stale)
    assert denied.status_code == 409
    assert planning_snapshot(customer_engine) == baseline
    second = generate(2, 1)
    assert second["inputs"]["goal"]["revision"] == raised
    assert second["inputs"]["total_ceiling_micros"] == 1_100_000_000
    assert second["inputs"]["aggressiveness"] == "assertive"
    for document, ceiling in ((first, 1_000_000_000), (second, 1_100_000_000)):
        alternatives = [
            s for s in document["scenarios"] if s["provenance"] == "customer_supplied_hypothesis"
        ]
        assert len(alternatives) == 2
        for scenario in alternatives:
            assert (
                sum(a["amount_micros"] for a in scenario["allocations"])
                + scenario["unallocated_micros"]
                == ceiling
            )
    calls_before_history = (len(fixture.native_calls), len(fixture.creative.calls))
    historical = alice.get(url + "/versions/1")
    assert historical.status_code == 200, historical.text
    assert PlanVersion.model_validate(historical.json()["document"]).digest() == first_digest
    for version, document in ((1, first), (2, second)):
        exported = alice.get(url + f"/export?version={version}")
        assert exported.status_code == 200, exported.text
        assert exported.json()["document"] == document
        assert exported.json()["document_digest"] == PlanVersion.model_validate(document).digest()
        (tmp_path / f"q07-{customer_engine.dialect.name}-v{version}-document.json").write_text(
            json.dumps(document, sort_keys=True)
        )
        (tmp_path / f"q07-{customer_engine.dialect.name}-v{version}-export.json").write_text(
            json.dumps(exported.json(), sort_keys=True)
        )
    assert (len(fixture.native_calls), len(fixture.creative.calls)) == calls_before_history
    assert financial_counts(customer_engine) == (0,) * 6
