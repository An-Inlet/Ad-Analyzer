"""Pure handoff contracts and actual shared-codec native/current semantic matching."""

from datetime import timedelta
from typing import Any

import httpx
import pytest
from app.collectors.meta_budget import MetaBudgetHTTP, NativeBudgetContext
from app.initial_planning.native_budget_contracts import (
    NativeBudgetObservationV1,
    NativeBudgetRequestV1,
)
from app.initial_planning.review_v2_contracts import (
    InitialPreviewExecutionIntentV1,
    InitialPreviewExecutionProofV1,
)
from app.initial_planning.review_v2_projection import native_review_match
from app.publication.optimization_contracts import MetaCurrentState
from pydantic import SecretStr, ValidationError

from tests.test_native_budget_contracts import request
from tests.test_planning_reporting_configuration import profile
from tests.test_provider_publication_contracts import NOW
from tests.test_social_optimization_http import setup


def pair() -> tuple[NativeBudgetObservationV1, MetaCurrentState]:
    _, server, original, _ = setup("meta_ads", campaign=True)
    current = original.before
    assert isinstance(current, MetaCurrentState)
    body = request().model_dump()
    body.update(scope=current.scope.model_dump(), target=current.target.model_dump())
    body["cohort"].update(
        workspace_id=current.scope.workspace_id, account_id=current.scope.account.account_id
    )
    native_request = NativeBudgetRequestV1.model_validate(body)
    reader = MetaBudgetHTTP(
        lambda req, now: NativeBudgetContext(
            request_digest=req.digest(),
            access_token=SecretStr("offline-token"),
            app_secret=None,
            expires_at=NOW + timedelta(hours=1),
            label="Campaign",
        ),
        profile().native_read,
        transport=httpx.MockTransport(server),
        clock=lambda: NOW,
    )
    observation = reader.read(native_request, NOW).options[0].observation
    assert not server.posts
    return observation, current


def test_actual_both_codecs_match_without_cast_or_authority() -> None:
    native, current = pair()
    before = native.model_dump_json()
    result = native_review_match(native, current)
    assert result.native_observation_digest == native.digest()
    assert result.qualified_state_digest == current.digest()
    assert native.model_dump_json() == before
    assert result.spending_authority == "none"
    changed_time = current.model_copy(update={"observed_at": NOW + timedelta(seconds=1)})
    assert native_review_match(native, changed_time) == result
    assert current.parent_configured_status == native.configured_status


@pytest.mark.parametrize(
    "field,value",
    [
        ("daily_budget_micros", 51_000_000),
        ("effective_status", "PAUSED"),
        ("configured_status", "PAUSED"),
        ("parent_configured_status", "PAUSED"),
        ("starts_at", NOW),
        ("ends_at", NOW + timedelta(days=1)),
        ("sharing_enabled", True),
        ("schedule_adjustments_enabled", True),
        ("rebalance_enabled", True),
        ("unaffected_settings_digest", "0" * 64),
        ("objective", "OUTCOME_TRAFFIC"),
        ("buying_type", "RESERVED"),
        ("complete", False),
        ("unsupported_features", ["unknown"]),
        ("lifetime_budget_micros", 100_000_000),
        ("account_status", "2"),
    ],
)
def test_changed_native_semantics_deny(field: str, value: Any) -> None:
    native, current = pair()
    with pytest.raises(ValueError):
        native_review_match(native, current.model_copy(update={field: value}))


@pytest.mark.parametrize("change", ["scope", "currency", "exponent", "timezone", "topology"])
def test_scope_money_topology_deny(change: str) -> None:
    native, current = pair()
    body = current.model_dump()
    if change == "scope":
        body["scope"]["connection_version"] = "changed"
    elif change == "topology":
        body["budget_owner"]["affected_targets"] = [body["target"]]
    else:
        key, value = {
            "currency": ("currency", "EUR"),
            "exponent": ("currency_exponent", 3),
            "timezone": ("account_timezone", "America/New_York"),
        }[change]
        body["money"][key] = value
    with pytest.raises(ValueError):
        native_review_match(native, MetaCurrentState.model_validate(body))


def proof() -> InitialPreviewExecutionProofV1:
    _, _, original, _ = setup("meta_ads", campaign=True)
    planning = original.intent.mandate.model_dump()
    execution = {**planning, "mandate_id": "8" * 32, "consent_id": "9" * 32}
    return InitialPreviewExecutionProofV1(
        workspace_id=1,
        preview_id="a" * 32,
        review_id="b" * 32,
        preview_digest="a" * 64,
        profile_digest="b" * 64,
        intent_digest="c" * 64,
        native_observation_digest="d" * 64,
        semantic_match_digest="e" * 64,
        planning_mandate=planning,
        execution_mandate=execution,
        qualified_state_digest="f" * 64,
        qualification_digest="1" * 64,
        plan_digest="2" * 64,
        created_at=NOW,
        expires_at=NOW + timedelta(seconds=10),
    )


def test_hash_only_proof_frozen_and_separate_same_ledger() -> None:
    value = proof()
    assert (
        value.digest()
        == InitialPreviewExecutionProofV1.model_validate_json(value.model_dump_json()).digest()
    )
    with pytest.raises(ValidationError):
        value.execution_mandate.__setattr__("ledger_id", "c" * 32)
    for field in ("mandate_id", "consent_id"):
        body = value.model_dump()
        body["execution_mandate"][field] = body["planning_mandate"][field]
        with pytest.raises(ValidationError):
            InitialPreviewExecutionProofV1.model_validate(body)
    for field, replacement in (("ledger_id", "c" * 32), ("environment", "live")):
        body = value.model_dump()
        body["execution_mandate"][field] = replacement
        with pytest.raises(ValidationError):
            InitialPreviewExecutionProofV1.model_validate(body)


def test_customer_intent_rejects_proof_and_money() -> None:
    body = {"expected_preview_digest": "a" * 64, "mandate_id": "b" * 32, "mandate_revision": 1}
    intent = InitialPreviewExecutionIntentV1.model_validate(body)
    assert (
        intent.digest()
        == InitialPreviewExecutionIntentV1.model_validate_json(intent.model_dump_json()).digest()
    )
    for key in ("amount_micros", "qualification_digest", "native_state", "ledger_id"):
        with pytest.raises(ValidationError):
            InitialPreviewExecutionIntentV1.model_validate({**body, key: "untrusted"})
