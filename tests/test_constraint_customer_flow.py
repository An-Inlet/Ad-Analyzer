"""Real customer routes/storage with explicitly injected candidate policy; synthetic providers."""

import json
import shutil
from copy import deepcopy
from functools import partial
from pathlib import Path
from typing import Any

import pytest
from app.api import customer_planning_documents as api
from app.lifecycle.privacy import bump_workspace_export_revision
from app.planning_documents.constraint_interpretation import LITERAL
from app.planning_documents.context import TargetRef
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import PlanEventRow, PlanInputRow, PlanVersionRow
from app.planning_documents.service import PlanningDocumentService
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_constraint_planning import candidate_policy
from tests.test_creative_common_basis import financial_counts
from tests.test_creative_q10_common_basis import _prepare
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import login
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_plan_target_picker import (
    test_target_picker_exact_choices_revocation_expiry_and_bounds as run_component,
)
from tests.test_shopify_sales import configuration as configuration


def prepare(
    engine: Engine, config: Settings, replicas: Any, patch: pytest.MonkeyPatch, path: Path
) -> Any:
    f, body, targets = _prepare(engine, config, replicas, patch, path, global_constraint=True)
    body["inputs"]["creative"]["product"].update(
        restrictions=[LITERAL],
        name="50% OFF! BUY NOW",
        customer_asserted_facts=["SAVE 20 USD TODAY"],
    )
    patch.setattr(
        api,
        "PlanningDocumentService",
        partial(
            PlanningDocumentService,
            policy=candidate_policy(),
            media_store=f.store,
        ),
    )
    root = f"/api/customer/v1/workspaces/{f.basis.workspace_id}/planning/plans"
    return f, body, targets, root


def assert_limits(doc: PlanVersion, original: dict[str, Any]) -> None:
    assert doc.inputs.total_ceiling_micros == 1_000_000_000
    assert doc.inputs.constraints == tuple(original["constraints"])
    assert doc.inputs.maximum_creative_assets == original["maximum_creative_assets"]
    assert doc.inputs.creative is not None
    assert doc.inputs.creative.model_dump(mode="json") == original["creative"]
    assert len(doc.inputs.accounts) == 1 and doc.inputs.accounts[0].platform == "meta_ads"
    for action in doc.actions:
        assert action.target.account == doc.inputs.accounts[0]
        if isinstance(action.target, TargetRef):
            assert action.target.provider_reference.entity_id != "5"
            assert action.target.provider_reference.parent_campaign_id != "5"
        assert action.native_budget is None and not action.proposed_fields
    for scenario in doc.scenarios:
        assert scenario.ceiling_micros == doc.inputs.total_ceiling_micros
        assert (
            sum(a.amount_micros for a in scenario.allocations) + scenario.unallocated_micros
            == scenario.ceiling_micros
        )
        for fixed in doc.inputs.fixed_allocations:
            assert [(a.target, a.amount_micros) for a in scenario.allocations] == [
                (fixed.target, fixed.amount_micros)
            ]
    assert not doc.advertising_writes_enabled and doc.spending_authority == "none"


def test_candidate_customer_review_history_export_correction_isolation_and_erasure(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    f, body, _, root = prepare(customer_engine, configuration, replicas, monkeypatch, tmp_path)
    alice, bob, provider = replicas
    counts = financial_counts(customer_engine)
    created = alice.post(root, headers=headers(alice), json=body)
    assert created.status_code == 201, created.text
    url = root + "/" + created.json()["plan_id"]
    request = dict(expected_input_revision=1, expected_version=0, request_key="q10-candidate-v1")
    generated = alice.post(url + "/generate", headers=headers(alice), json=request)
    assert generated.status_code == 200, generated.text
    first = generated.json()
    doc = PlanVersion.model_validate(first["document"])
    assert_limits(doc, body["inputs"])
    assert doc.constraint_interpretation is not None
    assert doc.constraint_interpretation.disposition == "fully_recognized"
    assert len(doc.briefs) == 1 and doc.briefs[0].hooks == ("Explore the product.",)
    assert len(doc.inputs.fixed_allocations) == 1
    assert doc.inputs.fixed_allocations[0].amount_micros == 200_000_000
    assert doc.inputs.fixed_allocations[0].target.provider_reference.entity_id == "7"
    current = alice.get(url)
    assert current.status_code == 200 and current.json()["freshness"] == "current", current.text
    assert current.json()["document"] == first["document"]
    assert doc.creative_composition is not None
    action = doc.creative_composition.proposals[0].action
    assert action.kind == "creative_review" and action in doc.actions
    decision = alice.post(
        url + "/decisions",
        headers=headers(alice),
        json=dict(
            expected_version=1,
            expected_event_sequence=0,
            document_digest=doc.digest(),
            action_key=action.key,
            action_digest=action.digest(),
            decision="deferred",
            reason="Review image claims and rights before publication",
            supersedes_event_id=None,
            request_key="q10-review-original",
        ),
    )
    assert decision.status_code == 200, decision.text
    assert decision.json()["event"]["action_digest"] == action.digest()
    native_reads = len(f.calls)
    replay = alice.post(url + "/generate", headers=headers(alice), json=request)
    assert replay.status_code == 200 and replay.json() == first
    assert len(f.calls) == native_reads
    corrected = deepcopy(body)
    corrected["inputs"]["constraints"].append("Do not use this image until rights are cleared.")
    corrected.update(expected_input_revision=1, expected_version=1, request_key="q10-correction")
    revised = alice.post(url + "/inputs", headers=headers(alice), json=corrected)
    assert revised.status_code == 200, revised.text
    second = alice.post(
        url + "/generate",
        headers=headers(alice),
        json=dict(
            expected_input_revision=2,
            expected_version=1,
            request_key="q10-candidate-v2",
        ),
    )
    assert second.status_code == 200, second.text
    next_doc = PlanVersion.model_validate(second.json()["document"])
    assert_limits(next_doc, corrected["inputs"])
    assert next_doc.parent_digest == doc.digest()
    assert next_doc.constraint_interpretation is not None
    assert next_doc.constraint_interpretation.disposition == "unresolved" and not next_doc.briefs
    assert any("Clarify" in s for s in next_doc.section_limitations)
    reads_after_generation = len(f.calls)
    # Regeneration may reuse retained source observations; it need not call the provider.
    assert reads_after_generation >= native_reads > 0
    # Historical recognition is independent of today's configured policy/default.
    monkeypatch.setattr(api, "PlanningDocumentService", PlanningDocumentService)
    for version, expected in ((1, first), (2, second.json())):
        for suffix in (f"/versions/{version}", f"/export?version={version}"):
            result = alice.get(url + suffix)
            assert result.status_code == 200, result.text
            assert result.json()["document"] == expected["document"]
            assert (
                result.json()["document_digest"]
                == PlanVersion.model_validate(expected["document"]).digest()
            )
    history = alice.get(url + "/versions")
    assert history.status_code == 200 and len(history.json()["items"]) == 2, history.text
    events = alice.get(url + "/events")
    assert events.status_code == 200 and len(events.json()["items"]) == 1
    assert events.json()["items"][0]["event"]["version"] == 1
    login(bob, "outsider:1")
    for suffix in ("", "/versions", "/events", "/export?version=1"):
        assert bob.get(url + suffix).status_code in {403, 404}
    (tmp_path / "constraint-documents.json").write_text(
        json.dumps([first["document"], second.json()["document"]])
    )
    for name in ("plan-document.mjs", "plan-constraints.mjs", "plan-reporting-comparability.mjs"):
        shutil.copy(Path("app/portal/static") / name, tmp_path / name)
    run_component(tmp_path, "plan_constraints_dom")
    provider.revoked.add("q16-owner")
    assert alice.get(url + "/export?version=1").status_code == 401
    provider.revoked.clear()
    with Session(customer_engine) as db, db.begin():
        bump_workspace_export_revision(db, f.basis.workspace_id)
    for model in (PlanInputRow, PlanVersionRow, PlanEventRow):
        with Session(customer_engine) as db:
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.workspace_id == f.basis.workspace_id)
                )
                == 0
            )
    assert financial_counts(customer_engine) == counts
    # This social fixture has one shared provider log; its transport asserts GET on every call.
    assert len(f.calls) == reads_after_generation
    (tmp_path / "q10-candidate-v1.json").write_text(doc.model_dump_json())
    (tmp_path / "q10-candidate-v2.json").write_text(next_doc.model_dump_json())


def test_infeasible_customer_constraints_remain_explicit(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    f, body, _, root = prepare(customer_engine, configuration, replicas, monkeypatch, tmp_path)
    alice, _, _ = replicas
    for variant in ("capacity", "asset", "product", "excluded"):
        changed = deepcopy(body)
        changed["request_key"] = "q10-infeasible-" + variant
        inputs = changed["inputs"]
        if variant == "capacity":
            inputs["maximum_creative_assets"] = 0
        elif variant == "asset":
            inputs["creative"]["media_selections"] = []
        elif variant == "product":
            inputs["creative"]["product"]["restrictions"].append("No images")
        else:
            inputs["exclusions"].append(inputs["fixed_allocations"][0]["target"])
            # A fixed allocation to an excluded target must be rejected, not removed.
        created = alice.post(root, headers=headers(alice), json=changed)
        if variant == "excluded":
            assert created.status_code in {409, 422}, created.text
            continue
        assert created.status_code == 201, created.text
        url = root + "/" + created.json()["plan_id"]
        result = alice.post(
            url + "/generate",
            headers=headers(alice),
            json=dict(
                expected_input_revision=1,
                expected_version=0,
                request_key="generate-" + variant,
            ),
        )
        assert result.status_code == 200, result.text
        doc = PlanVersion.model_validate(result.json()["document"])
        assert_limits(doc, inputs)
        assert not doc.briefs
        assert any("Deferred:" in text for text in doc.section_limitations)
        assert doc.creative_proof is not None
        if variant == "asset":
            assert not doc.creative_proof.basis.images
    over = deepcopy(body)
    over["request_key"] = "q10-over-ceiling"
    over["inputs"]["fixed_allocations"][0]["amount_micros"] = 1_000_000_001
    rejected = alice.post(root, headers=headers(alice), json=over)
    assert rejected.status_code == 422, rejected.text
    assert financial_counts(customer_engine) == (0,) * 6
