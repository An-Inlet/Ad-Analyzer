"""Private V6 actual API qualification; no native mutation or period-cap claim."""

import json
from pathlib import Path
from typing import Any, cast

import pytest
from app.customers.access import SESSION_COOKIE
from app.planning_documents.documents import PlanVersion
from app.settings import Settings
from sqlalchemy import Engine
from sqlalchemy.engine import CursorResult

from tests.creative_q07_fixture import planning_snapshot
from tests.owner_review_runtime_fixture import (
    add_owned_meta,
    configured_owner_review,
    confirm_zero_goal,
)
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def generation() -> dict[str, Any]:
    return dict(expected_input_revision=1, expected_version=0, request_key="owner-v6-generate")


@pytest.mark.parametrize("variant", ["owner", "empty", "zero", "unselected-meta", "mixed-meta"])
def test_actual_owner_review_generation_history_export_replay(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    variant: str,
) -> None:
    fixture, body, calls, _ = configured_owner_review(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    alice, _, _ = replicas
    original_cookie = alice.cookies[SESSION_COOKIE]
    meta_id = None
    if variant in {"unselected-meta", "mixed-meta"}:
        meta_id = add_owned_meta(
            customer_engine, alice, fixture, body, monkeypatch, linked=variant == "mixed-meta"
        )
    if variant == "zero":
        confirm_zero_goal(alice, fixture, body)
    if variant == "empty":
        body["inputs"]["google_daily_budget_intents"] = []
    root = f"/api/customer/v1/workspaces/{fixture.basis.workspace_id}/planning/plans"
    before_effects = financial_counts(customer_engine)
    response = alice.post(root, headers=headers(alice), json=body)
    assert response.status_code == 201, response.text
    saved_input = response.json()
    url = root + "/" + saved_input["plan_id"]
    response = alice.post(url + "/generate", headers=headers(alice), json=generation())
    assert response.status_code == 200, response.text
    result = response.json()
    document = PlanVersion.model_validate(result["document"])
    from app.planning_documents.models import PlanVersionRow
    from app.planning_documents.storage import plan_version_storage_pair
    from sqlalchemy.orm import Session

    with Session(customer_engine) as db:
        stored = db.get(
            PlanVersionRow,
            (document.inputs.workspace_id, document.inputs.plan_id, document.version),
        )
        assert stored is not None
        assert (stored.canonical_json, stored.digest) == plan_version_storage_pair(document)
    assert document.policy_version == "inlet.descriptive-review.v6"
    assert document.google_budget_owner_review is not None
    assert document.google_budget_input_catalogs is not None
    if meta_id is not None:
        assert document.selected_reporting_proof is not None
        assert {
            a.source_fence.account.account_id for a in document.selected_reporting_proof.accounts
        } == {fixture.basis.account_id, meta_id}
        linked_ids = {
            c.reference.account.account_id
            for c in document.google_budget_input_catalogs
            if c.reference.account is not None
        }
        assert linked_ids == (
            {fixture.basis.account_id, meta_id}
            if variant == "mixed-meta"
            else {fixture.basis.account_id}
        )
    assert len(document.google_budget_owner_review.reviews) == (0 if variant == "empty" else 1)
    if variant == "zero":
        assert document.inputs.total_ceiling_micros == 0
        assert all(
            a.amount_micros == 0
            for scenario in document.inputs.scenario_intents
            for a in scenario.allocations
        )
        assert all(s.unallocated_micros == 0 for s in document.inputs.scenario_intents)
        assert document.google_budget_owner_review.reviews[0].intent.requested_amount_micros == 0
    if variant == "mixed-meta":
        allocation = document.inputs.scenario_intents[0].allocations[1]
        intended = body["inputs"]["scenario_intents"][0]["allocations"][1]
        assert allocation.target.account.account_id == meta_id
        assert allocation.target.canonical_entity_key == intended["target"]["canonical_entity_key"]
        assert allocation.target.selection_key == intended["target"]["selection_key"]
        assert allocation.amount_micros == intended["amount_micros"] == 50_000_000
        assert document.inputs.excluded_entity_keys == tuple(
            x["canonical_entity_key"] for x in body["inputs"]["exclusions"]
        )
    for review in document.google_budget_owner_review.reviews:
        action = next(a for a in document.actions if a.key == review.action_key)
        assert (
            action.kind == "investigate"
            and action.proposed_fields == ()
            and action.native_budget is None
        )
        assert "Do not apply" in action.rationale
    before = (len(calls), len(fixture.calls), planning_snapshot(customer_engine))
    replay = alice.post(url + "/generate", headers=headers(alice), json=generation())
    assert replay.status_code == 200 and replay.json() == result, replay.text
    current = alice.get(url)
    assert current.status_code == 200, current.text
    assert current.json()["document"] == result["document"]
    assert current.json()["freshness"] == "current"
    version = alice.get(url + "/versions/1")
    assert version.status_code == 200 and version.json()["document"] == result["document"]
    exported = alice.get(url + "/export?version=1")
    assert exported.status_code == 200 and exported.json()["document"] == result["document"]
    assert PlanVersion.model_validate(exported.json()["document"]).digest() == document.digest()
    lookup = alice.get(root + "/requests/generate/owner-v6-generate")
    assert lookup.status_code == 200 and lookup.json() == result
    assert (len(calls), len(fixture.calls), planning_snapshot(customer_engine)) == before
    assert financial_counts(customer_engine) == before_effects
    assert alice.cookies[SESSION_COOKIE] == original_cookie
    (tmp_path / f"owner-{variant}-document.json").write_text(
        document.model_dump_json(indent=2) + "\n"
    )
    (tmp_path / f"owner-{variant}-export.json").write_text(
        json.dumps(exported.json(), indent=2) + "\n"
    )


def test_private_owner_policy_requires_explicit_tuple_before_provider_io(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fixture, body, calls, _ = configured_owner_review(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    alice, _, _ = replicas
    body["inputs"].pop("google_daily_budget_intents")
    before = (
        len(calls),
        len(fixture.calls),
        planning_snapshot(customer_engine),
        financial_counts(customer_engine),
    )
    root = f"/api/customer/v1/workspaces/{fixture.basis.workspace_id}/planning/plans"
    response = alice.post(root, headers=headers(alice), json=body)
    assert response.status_code == 409
    assert response.json()["detail"] == "explicit Google budget owner hypotheses required"
    assert (
        len(calls),
        len(fixture.calls),
        planning_snapshot(customer_engine),
        financial_counts(customer_engine),
    ) == before


def test_actual_save_rejects_strict_valid_substituted_linked_catalog(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app.planning_documents import repository
    from app.planning_documents.catalog_evidence import CatalogEvidence
    from app.planning_documents.owner_review_generation import assert_owner_review_generation_bundle
    from app.planning_documents.owner_review_plan_composer import OwnerReviewPlanComposer

    fixture, body, _, _ = configured_owner_review(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    alice, _, _ = replicas
    meta_id = add_owned_meta(customer_engine, alice, fixture, body, monkeypatch, linked=True)
    root = f"/api/customer/v1/workspaces/{fixture.basis.workspace_id}/planning/plans"
    saved = alice.post(root, headers=headers(alice), json=body)
    assert saved.status_code == 201, saved.text
    url = root + "/" + saved.json()["plan_id"]
    before = planning_snapshot(customer_engine), financial_counts(customer_engine)
    original = OwnerReviewPlanComposer.compose
    changed: list[bool] = []

    def substitute(self: OwnerReviewPlanComposer, **kwargs: Any) -> PlanVersion:
        document = original(self, **kwargs)
        assert document.google_budget_input_catalogs is not None
        raw = document.model_dump(mode="python")
        before_ticket = kwargs["ticket"].model_dump_json()
        before_evidence = kwargs["evidence"].model_dump_json()
        assert document.google_budget_owner_review is not None
        assert len(document.google_budget_owner_review.reviews) == 1
        before_owner = document.google_budget_owner_review.model_dump_json()
        before_inputs = document.inputs.model_dump_json()
        original_catalogs = tuple(
            c.model_dump_json() for c in document.google_budget_input_catalogs
        )
        matches = [
            (index, catalog)
            for index, catalog in enumerate(raw["google_budget_input_catalogs"])
            if catalog["reference"]["account"]["account_id"] == meta_id
            and catalog["reference"]["account"]["workspace_id"] == fixture.basis.workspace_id
            and catalog["reference"]["account"]["platform"] == "meta_ads"
        ]
        assert len(matches) == 1
        index, catalog = matches[0]
        campaign_rows = [
            row
            for row in catalog["catalog"]["native_observation"]["targets"]
            if row["kind"] == "campaign"
        ]
        assert len(campaign_rows) == 2
        settings = campaign_rows[0]["settings"]
        assert settings["platform"] == "meta_ads"
        old_cap = settings["spend_cap_native"]
        settings["spend_cap_native"] = 1 if old_cap is None else old_cap + 1
        checked_catalog = CatalogEvidence.model_validate(catalog)
        assert checked_catalog.model_dump_json() != original_catalogs[index]
        candidate = PlanVersion.model_validate(raw)
        assert candidate.digest() != document.digest()
        assert candidate.inputs.model_dump_json() == before_inputs
        assert candidate.google_budget_owner_review is not None
        assert candidate.google_budget_owner_review.model_dump_json() == before_owner
        assert candidate.google_budget_input_catalogs is not None
        assert all(
            c.model_dump_json() == original_catalogs[i]
            for i, c in enumerate(candidate.google_budget_input_catalogs)
            if i != index
        )
        # Revert the sole changed leaf and require exact full-document equality.
        settings["spend_cap_native"] = old_cap
        assert PlanVersion.model_validate(raw).model_dump_json() == document.model_dump_json()
        assert kwargs["ticket"].model_dump_json() == before_ticket
        assert kwargs["evidence"].model_dump_json() == before_evidence
        assert (
            tuple(c.model_dump_json() for c in kwargs["evidence"].reporting.selected.catalogs)
            == original_catalogs
        )
        changed.append(True)
        return candidate

    reached: list[bool] = []
    actual_binding = assert_owner_review_generation_bundle

    def check_actual(**kwargs: Any) -> None:
        reached.append(True)
        actual_binding(**kwargs)

    monkeypatch.setattr(repository, "assert_owner_review_generation_bundle", check_actual)
    monkeypatch.setattr(OwnerReviewPlanComposer, "compose", substitute)
    response = alice.post(url + "/generate", headers=headers(alice), json=generation())
    assert changed == [True]
    assert reached == [True]
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "owner review differs from actual collected evidence"
    assert (planning_snapshot(customer_engine), financial_counts(customer_engine)) == before


@pytest.mark.parametrize("fault", ["new-session", "final-receipt", "post-flush"])
def test_owner_generation_original_receipt_and_atomic_rollback(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fault: str,
) -> None:
    from app.planning_documents import owner_review_generation, repository
    from app.planning_documents.catalog_receipt_models import CatalogReceiptRow
    from app.planning_documents.models import PlanVersionRow
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session

    from tests.test_customer_identity import login

    fixture, body, _, _ = configured_owner_review(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    alice, _, _ = replicas
    root = f"/api/customer/v1/workspaces/{fixture.basis.workspace_id}/planning/plans"
    saved = alice.post(root, headers=headers(alice), json=body)
    assert saved.status_code == 201, saved.text
    url = root + "/" + saved.json()["plan_id"]
    before = planning_snapshot(customer_engine), financial_counts(customer_engine)
    observed: list[bool] = []
    expiry: list[Any] = []
    in_final = False
    if fault == "new-session":
        cookie = alice.cookies[SESSION_COOKIE]
        login(alice, "q16-owner:v6-replacement")
        assert alice.cookies[SESSION_COOKIE] != cookie
    elif fault == "final-receipt":
        original_resolve = cast(Any, owner_review_generation).resolve_saved_input_catalogs
        original_scalar = Session.scalar

        def resolve(*args: Any, **kwargs: Any) -> Any:
            nonlocal in_final
            in_final = True
            try:
                return original_resolve(*args, **kwargs)
            finally:
                in_final = False

        def scalar(db: Session, *args: Any, **kwargs: Any) -> Any:
            row = original_scalar(db, *args, **kwargs)
            if in_final and isinstance(row, CatalogReceiptRow):
                # Fault the actual loaded original scalar, not current principal,
                # database state, returned proof, callback or original auth clock.
                db.expunge(row)
                row.session_digest = "f" * 64
                observed.append(True)
            return row

        monkeypatch.setattr(owner_review_generation, "resolve_saved_input_catalogs", resolve)
        monkeypatch.setattr(Session, "scalar", scalar)
    else:
        original_flush = Session.flush
        original_clock = cast(Any, repository).database_utc_now

        def flush(db: Session, *args: Any, **kwargs: Any) -> None:
            pending = [r.valid_until for r in db.new if isinstance(r, PlanVersionRow)]
            original_flush(db, *args, **kwargs)
            if pending:
                assert db.scalar(select(func.count()).select_from(PlanVersionRow)) == 1
                expiry.extend(pending)
                observed.append(True)

        monkeypatch.setattr(Session, "flush", flush)
        monkeypatch.setattr(
            repository, "database_utc_now", lambda db: expiry[0] if expiry else original_clock(db)
        )
    response = alice.post(url + "/generate", headers=headers(alice), json=generation())
    assert response.status_code == 409, response.text
    if fault == "post-flush":
        assert observed == [True]
        assert response.json()["detail"] == "generation evidence expired"
    else:
        assert response.json()["detail"] == (
            "The exact catalog selection is unavailable. Read fresh targets and explicitly "
            "save a new input revision before generating a plan."
        )
        if fault == "final-receipt":
            assert observed == [True]
    assert (planning_snapshot(customer_engine), financial_counts(customer_engine)) == before


def test_generated_owner_history_requires_original_input_links(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app.planning_documents.catalog_receipt_models import InputCatalogReceiptRow
    from sqlalchemy import delete
    from sqlalchemy.orm import Session

    fixture, body, calls, _ = configured_owner_review(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    alice, _, _ = replicas
    root = f"/api/customer/v1/workspaces/{fixture.basis.workspace_id}/planning/plans"
    saved = alice.post(root, headers=headers(alice), json=body)
    assert saved.status_code == 201, saved.text
    url = root + "/" + saved.json()["plan_id"]
    generated = alice.post(url + "/generate", headers=headers(alice), json=generation())
    assert generated.status_code == 200, generated.text
    with Session(customer_engine) as db, db.begin():
        deleted = db.execute(
            delete(InputCatalogReceiptRow).where(
                InputCatalogReceiptRow.workspace_id == fixture.basis.workspace_id,
                InputCatalogReceiptRow.plan_id == saved.json()["plan_id"],
            )
        )
        assert cast(CursorResult[Any], deleted).rowcount == 1
    # Actual supported dependency deletion, not broad workspace-erasure qualification.
    baseline = (
        planning_snapshot(customer_engine),
        financial_counts(customer_engine),
        len(calls),
        len(fixture.calls),
    )
    responses = [
        alice.get(url),
        alice.get(url + "/versions/1"),
        alice.get(url + "/export?version=1"),
        alice.post(url + "/generate", headers=headers(alice), json=generation()),
    ]
    assert all(r.status_code == 409 for r in responses), [r.status_code for r in responses]
    assert [r.json()["detail"] for r in responses] == [
        "The original budget owner input proof is unavailable.",
        "The original budget owner input proof is unavailable.",
        "The original budget owner input proof is unavailable.",
        "selected plan historical integrity unavailable",
    ]
    assert (
        planning_snapshot(customer_engine),
        financial_counts(customer_engine),
        len(calls),
        len(fixture.calls),
    ) == baseline
