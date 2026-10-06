"""Explicit fixture policy; no live registry or execution authority."""

from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal

import pytest
from app.commerce.evidence import digest
from app.outcomes.contracts import Window
from app.outcomes.feedback import (
    FeedbackContribution,
    FeedbackDecisionPolicy,
    decision_policy_for,
    prepare_feedback,
    recompute_active_score,
)
from app.outcomes.owned_v3 import OwnedV3Assessment, OwnedV3Request, _snapshot, compare_owned_v3
from app.publication.service import owner
from app.settings import Settings
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_owned_outcomes import evidence
from tests.test_owned_outcomes_v3 import facts
from tests.test_owned_outcomes_v3 import policy as maturity_policy
from tests.test_shopify_sales import configuration as configuration


def make_assessment(
    customer_engine: Engine, configuration: Settings, tmp_path: Path
) -> OwnedV3Assessment:
    with Session(customer_engine) as db:
        wid, actor, body, _, _ = evidence(db, configuration, tmp_path)
        request = OwnedV3Request.model_validate(body.model_dump(exclude={"policy_id"}))
        snap = _snapshot(db, wid, actor, request, lambda db: owner(db, wid, actor), lambda: NOW)
    boundary = Window.local(
        request.before_start, request.before_end, snap.context.scope.time_zone
    ).end_utc
    snap = snap.model_copy(
        update={
            "receipt": snap.receipt.model_copy(
                update={
                    "purpose": "activate",
                    "outcome": "verified_effect",
                    "dispatched_at": boundary,
                    "observed_at": boundary + timedelta(minutes=1),
                    "effective_lower": boundary,
                    "effective_upper": boundary,
                    "effective_time_evidence": "authoritative_interval",
                }
            )
        }
    )
    return compare_owned_v3(
        snap,
        request,
        maturity_policy(snap.context),
        facts(snap.context, request.before_start, request.before_end, 10),
        facts(snap.context, request.after_start, request.after_end, 15),
    )


@pytest.fixture
def assessment(
    customer_engine: Engine, configuration: Settings, tmp_path: Path
) -> OwnedV3Assessment:
    return make_assessment(customer_engine, configuration, tmp_path)


def policy(assessment: OwnedV3Assessment) -> FeedbackDecisionPolicy:
    scope = assessment.context.scope
    return FeedbackDecisionPolicy(
        family="synthetic_score_fixture",
        version=1,
        metric_definition_digest=scope.metric_definition_digest,
        currency=scope.currency,
        time_zone=scope.time_zone,
        preferred_direction="higher",
        minimum_absolute_relative_signal=Decimal("0.1"),
        score_gain=Decimal("1"),
        maximum_absolute_contribution=Decimal("0.2"),
        maximum_absolute_total=Decimal("0.3"),
        allowed_purposes=("activate", "existing_campaign_optimize"),
    )


def test_preparation_is_policy_gated_bounded_and_environment_bound(
    assessment: OwnedV3Assessment,
) -> None:
    configured = policy(assessment)
    fingerprint = digest(assessment.model_dump(mode="json"))
    assert decision_policy_for(configured.family) is None

    def prepare(
        chosen: FeedbackDecisionPolicy | None,
        environment: Literal["contract_test", "live"] = "contract_test",
    ) -> FeedbackContribution:
        return prepare_feedback(
            assessment, chosen, environment=environment, expected_assessment_digest=fingerprint
        )

    assert prepare(None).reasons == ("decision_policy_unavailable",)
    higher = prepare(configured)
    assert higher.status == "eligible" and higher.score == Decimal("0.2")
    assert higher.spending_authority == "none"
    lower = prepare(configured.model_copy(update={"preferred_direction": "lower"}))
    assert lower.score == Decimal("-0.2")
    assert "assessment_environment_mismatch" in prepare(configured, "live").reasons
    assert (
        "signal_below_policy_threshold"
        in prepare(
            configured.model_copy(
                update={
                    "minimum_absolute_relative_signal": Decimal(
                        "0.50000000000000000000000000000000000000000000000000000000000000001"
                    )
                }
            )
        ).reasons
    )
    assert (
        "decision_policy_basis_mismatch"
        in prepare(configured.model_copy(update={"currency": "EUR"})).reasons
    )
    wrong = prepare_feedback(
        assessment, configured, environment="contract_test", expected_assessment_digest="0" * 64
    )
    assert wrong.status == "ineligible" and wrong.score is None


def test_recompute_is_idempotent_noncompounding_and_retraction_removes_score(
    assessment: OwnedV3Assessment,
) -> None:
    configured = policy(assessment)
    first = prepare_feedback(
        assessment,
        configured,
        environment="contract_test",
        expected_assessment_digest=digest(assessment.model_dump(mode="json")),
    )
    second = first.model_copy(update={"original_attempt_id": "a" * 32})

    for _ in range(3):
        assert recompute_active_score(
            configured,
            (first, second),
            workspace_id=assessment.context.scope.workspace_id,
            environment="contract_test",
        ) == Decimal("0.3")
    assert recompute_active_score(
        configured,
        (first,),
        workspace_id=assessment.context.scope.workspace_id,
        environment="contract_test",
    ) == Decimal("0.2")
    assert (
        recompute_active_score(
            configured,
            (),
            workspace_id=assessment.context.scope.workspace_id,
            environment="contract_test",
        )
        == 0
    )
    for bad in (
        first,
        second.model_copy(update={"workspace_id": 999}),
        second.model_copy(update={"environment": "live"}),
        second.model_copy(update={"policy_digest": "0" * 64}),
    ):
        with pytest.raises(ValueError):
            recompute_active_score(
                configured,
                (first, bad),
                workspace_id=assessment.context.scope.workspace_id,
                environment="contract_test",
            )
