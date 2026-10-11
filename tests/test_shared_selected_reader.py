"""Genuine reserved-v5 reporting collection does not enable v5 composition."""

from typing import Any

import pytest
from app.planning_documents.context import PlanInputRevision
from app.planning_documents.creative_basis import CreativeInputV1
from app.planning_documents.documents import PlanVersion
from app.planning_documents.policy_capabilities import reporting_capability
from app.planning_documents.ports import GenerationTicket, PlanningCompositionPolicy
from app.planning_documents.selected_composer import SelectedPlanComposer
from app.planning_documents.selected_paired_reader import OwnedSelectedPairedReader
from app.planning_documents.selected_plan_adapter import OwnedSelectedEvidenceReader
from app.planning_documents.selected_plan_bundle import SelectedPlanEvidenceBundleV1
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine

from tests.selected_range_plan_fixture import prepared_range_plan
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_selected_plan_bundle import ready
from tests.test_shopify_sales import configuration as configuration


def genuine_v5(ticket: GenerationTicket) -> tuple[GenerationTicket, PlanningCompositionPolicy]:
    policy = PlanningCompositionPolicy(
        version="inlet.descriptive-review.v5", generator_version="inlet.descriptive-planning.v5"
    )
    values = ticket.inputs.model_dump()
    values["creative"] = CreativeInputV1()
    inputs = PlanInputRevision.model_validate(values)
    return GenerationTicket.model_validate(
        {
            **ticket.model_dump(),
            "inputs": inputs,
            "policy_version": policy.version,
            "policy_digest": policy.digest(),
        }
    ), policy


def test_pure_genuine_v5_bundle_and_unchanged_v4_bytes() -> None:
    ticket, original = ready()
    before = original.model_dump_json(), original.digest()
    original.assert_ticket(ticket)
    actual, policy = genuine_v5(ticket)
    bundle = SelectedPlanEvidenceBundleV1.model_validate(
        {**original.model_dump(), "input_digest": actual.inputs.digest()}
    )
    bundle.assert_ticket(actual)
    assert bundle.reporting_proof == original.reporting_proof
    assert (original.model_dump_json(), original.digest()) == before
    with pytest.raises(ValueError):
        reporting_capability(policy.version, policy.generator_version)


@pytest.mark.parametrize("empty", [False, True])
def test_actual_paired_reader_preserves_genuine_v5_context(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    empty: bool,
) -> None:
    old, ticket, _, _, _ = prepared_range_plan(
        customer_engine, configuration, replicas, monkeypatch
    )
    legacy = OwnedSelectedPairedReader(
        old.sessions,
        principal=old.principal,
        provider=old.provider,
        policy=old.policy,
        clock=old.clock,
    ).collect(ticket)
    actual, policy = genuine_v5(ticket)
    if empty:
        actual = GenerationTicket.model_validate(
            actual.model_copy(
                update={"inputs": actual.inputs.model_copy(update={"selected_reporting": ()})}
            )
        )
    reader = OwnedSelectedPairedReader(
        old.sessions,
        principal=old.principal,
        provider=old.provider,
        policy=policy,
        clock=old.clock,
    )
    bundle = reader.collect(actual)
    bundle.assert_ticket(actual)
    context = {item.reference.kind: item.document for item in bundle.selected.context}
    assert context == {"customer_context": actual.inputs, "planning_policy": policy}
    assert actual.inputs.creative == CreativeInputV1()
    if empty:
        assert actual.inputs.selected_reporting == ()
        assert not bundle.selected.selected_captures
        assert {g.reason for g in bundle.selected.window_gaps} == {"selected_capture_not_requested"}
    else:
        assert bundle.selected.reporting_proof == legacy.selected.reporting_proof
        # Each native collection has a fresh catalog expiry and selection key
        # bound to that catalog composite. assert_ticket above verifies those
        # exact per-collection keys; reporting content remains identical.
        for current, previous in zip(
            bundle.selected.performance, legacy.selected.performance, strict=True
        ):
            assert current.model_dump(
                exclude={"reference": {"expires_at"}, "target": {"selection_key"}}
            ) == previous.model_dump(
                exclude={"reference": {"expires_at"}, "target": {"selection_key"}}
            )
        for current_traffic, previous_traffic in zip(bundle.traffic, legacy.traffic, strict=True):
            assert current_traffic.model_dump(
                exclude={"reference": {"expires_at"}, "target": {"selection_key"}}
            ) == previous_traffic.model_dump(
                exclude={"reference": {"expires_at"}, "target": {"selection_key"}}
            )
    with pytest.raises(ValueError):
        reporting_capability(policy.version, policy.generator_version)
    with pytest.raises(ValueError):
        SelectedPlanComposer().compose(
            ticket=actual, evidence=bundle, policy=policy, generated_at=old.clock()
        )
    old_document = SelectedPlanComposer().compose(
        ticket=ticket, evidence=legacy, policy=old.policy, generated_at=old.clock()
    )
    with pytest.raises(ValueError):
        PlanVersion.model_validate(
            {
                **old_document.model_dump(),
                "inputs": actual.inputs,
                "policy_version": policy.version,
                "generator_version": policy.generator_version,
            }
        )


@pytest.mark.parametrize(
    "change", ["mixed", "digest", "missing_creative", "missing_selected", "altered"]
)
def test_invalid_policy_before_any_io(change: str) -> None:
    from unittest.mock import Mock

    ticket, _ = ready()
    ticket, policy = genuine_v5(ticket)
    if change == "mixed":
        policy = policy.model_copy(update={"generator_version": "inlet.descriptive-planning.v4"})
    elif change == "digest":
        ticket = ticket.model_copy(update={"policy_digest": "0" * 64})
    elif change == "altered":
        policy = policy.model_copy(update={"native_writes": "available"})
    else:
        ticket = ticket.model_copy(
            update={
                "inputs": ticket.inputs.model_copy(
                    update={
                        "creative" if change == "missing_creative" else "selected_reporting": None
                    }
                )
            }
        )
    # Constructor snapshots original identity; bypass only constructor to probe the
    # public method's pure pre-I/O boundary without fabricating an owned principal.
    reader = OwnedSelectedEvidenceReader.__new__(OwnedSelectedEvidenceReader)
    reader.policy = policy
    reader.sessions = Mock(side_effect=AssertionError("SQL must not start"))
    with pytest.raises(HTTPException) as error:
        reader.collect(ticket)
    assert error.value.status_code == 409
    reader.sessions.assert_not_called()
