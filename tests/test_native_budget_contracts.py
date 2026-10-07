"""Unqualified read commitment cannot be mistaken for execution state."""

from datetime import UTC, datetime, timedelta

import pytest
from app.initial_planning.native_budget_contracts import (
    NativeBudgetCatalogV1,
    NativeBudgetObservationV1,
    NativeBudgetOptionV1,
    NativeBudgetRequestV1,
)
from app.publication.contracts import fingerprint
from app.publication.optimization_contracts import MetaCurrentState
from pydantic import ValidationError


def request() -> NativeBudgetRequestV1:
    return NativeBudgetRequestV1.model_validate(
        {
            "profile_digest": "a" * 64,
            "environment": "contract_test",
            "scope": {
                "workspace_id": 1,
                "account": {
                    "account_id": 2,
                    "connection_id": 3,
                    "platform": "meta_ads",
                },
                "external_advertiser_id": "4",
                "connection_version": "1",
            },
            "cohort": {
                "workspace_id": 1,
                "account_id": 2,
                "campaign_id": 5,
                "selected_event": "purchase",
                "currency": "USD",
                "time_zone": "UTC",
                "query_version": "meta.v26.0.campaign-day.v1",
            },
            "goal_id": "b" * 32,
            "goal_revision": 1,
            "goal_digest": "c" * 64,
            "target": {"kind": "campaign", "external_id": "6", "campaign_id": "6"},
        }
    )


def observation() -> NativeBudgetObservationV1:
    req = request()
    target = req.target.model_dump()
    now = datetime(2026, 10, 7, tzinfo=UTC)
    return NativeBudgetObservationV1.model_validate(
        {
            "request": req.model_dump(),
            "budget_owner": {
                "provider": "meta_ads",
                "owner": target,
                "mode": "campaign_pool",
                "affected_targets": [target],
                "topology_digest": fingerprint(
                    "inlet.optimization-topology.v1", {"targets": [target]}
                ),
            },
            "currency": "USD",
            "currency_exponent": 2,
            "time_zone": "UTC",
            "budget_mode": "daily",
            "amount_micros": 5000000,
            "account_status": "1",
            "configured_status": "ACTIVE",
            "effective_status": "ACTIVE",
            "starts_at": None,
            "ends_at": None,
            "sharing_enabled": False,
            "schedule_adjustments_enabled": False,
            "rebalance_enabled": False,
            "unaffected_settings_digest": "d" * 64,
            "unsupported_reasons": [],
            "observation_started_at": now,
            "observed_at": now,
            "expires_at": now + timedelta(seconds=30),
        }
    )


def test_read_has_no_financial_period_or_qualification_and_is_deeply_frozen() -> None:
    value = observation()
    assert "qualification_id" not in value.model_dump_json()
    assert "period_start" not in value.model_dump_json()
    assert value.spending_authority == "none"
    with pytest.raises(ValidationError):
        MetaCurrentState.model_validate(value.model_dump())
    with pytest.raises(ValidationError):
        value.request.scope.account.__setattr__("account_id", 9)
    with pytest.raises(ValidationError):
        value.budget_owner.owner.__setattr__("external_id", "9")
    assert isinstance(value.budget_owner.affected_targets, tuple)


@pytest.mark.parametrize(
    "change", ["scope", "currency", "topology", "expiry", "flags", "authority"]
)
def test_observation_bindings(change: str) -> None:
    value = observation().model_dump(mode="json")
    if change == "scope":
        value["request"]["scope"]["workspace_id"] = 99
    elif change == "currency":
        value["currency"] = "EUR"
    elif change == "topology":
        value["budget_owner"]["topology_digest"] = "0" * 64
    elif change == "expiry":
        value["expires_at"] = value["observed_at"]
    elif change == "flags":
        value["sharing_enabled"] = None
    else:
        value["spending_authority"] = "approved"
    with pytest.raises(ValidationError):
        NativeBudgetObservationV1.model_validate(value)


def test_exact_option_catalog_and_opaque_id() -> None:
    obs = observation()
    option = NativeBudgetOptionV1(label="Owned Campaign", observation=obs)
    catalog = NativeBudgetCatalogV1(
        request=obs.request,
        options=(option,),
        observed_at=obs.observed_at,
        expires_at=obs.expires_at,
    )
    assert len(option.identifier()) == 64 and catalog.complete
    unsupported = obs.model_dump()
    unsupported["unsupported_reasons"] = ("account_not_active",)
    with pytest.raises(ValidationError):
        NativeBudgetOptionV1(
            label="Unsupported", observation=NativeBudgetObservationV1.model_validate(unsupported)
        )
    body = catalog.model_dump()
    body["request"]["goal_revision"] = 2
    with pytest.raises(ValidationError):
        NativeBudgetCatalogV1.model_validate(body)
