"""Data-boundary unit examples only; these fabricated IDs never authorize or seed SQL."""

from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError

from tests.google_created_retained_fixture import GoogleCreatedIds


def example() -> dict[str, Any]:
    values: dict[str, Any] = {
        name: "a" * 32
        for name in (
            "actor_id",
            "run_id",
            "review_id",
            "mandate_id",
            "consent_id",
            "ledger_id",
            "reservation_id",
            "native_connection_id",
        )
    }
    values.update(
        {
            name: 1
            for name in (
                "workspace_id",
                "account_id",
                "mandate_revision",
                "reservation_amount_micros",
                "provider_posts",
            )
        }
    )
    values.update(
        {
            name: "b" * 64
            for name in (
                "policy_digest",
                "review_digest",
                "plan_digest",
            )
        }
    )
    values.update(
        mode="daily_completed",
        attempts=[
            dict(
                step_id="budget",
                attempt_id="a" * 32,
                fence="a" * 32,
                request_digest="b" * 64,
                response_digest="b" * 64,
                latest_receipt_id="a" * 32,
                latest_receipt_digest="b" * 64,
                latest_receipt_sequence=1,
                completion_digest="b" * 64,
                resource_name="customers/1234567890/campaignBudgets/1",
            )
        ],
    )
    return values


@pytest.mark.parametrize("mode", ["daily_completed", "daily_unknown"])
def test_only_closed_daily_shapes_roundtrip(mode: str) -> None:
    data = example()
    data["mode"] = mode
    if mode == "daily_unknown":
        data["attempts"][0].update(completion_digest=None, resource_name=None)
    parsed = GoogleCreatedIds.model_validate(data)
    assert GoogleCreatedIds.model_validate_json(parsed.model_dump_json()) == parsed


@pytest.mark.parametrize(
    "change",
    [
        "bool",
        "string",
        "zero",
        "extra",
        "mode",
        "posts",
        "bool_posts",
        "no_attempt",
        "extra_attempt",
        "bad_hex",
        "no_completion",
        "no_resource",
        "long_resource",
        "nested_extra",
        "nested_bool",
    ],
)
def test_untrusted_scalar_shapes_reject(change: str) -> None:
    data = deepcopy(example())
    pin = data["attempts"][0]
    if change in {"bool", "string", "zero"}:
        data["workspace_id"] = {"bool": True, "string": "1", "zero": 0}[change]
    elif change == "extra":
        data["authority"] = "none"
    elif change == "mode":
        data["mode"] = "total_created"
    elif change in {"posts", "bool_posts"}:
        data["provider_posts"] = 2 if change == "posts" else True
    elif change == "no_attempt":
        data["attempts"] = []
    elif change == "extra_attempt":
        data["attempts"].append(deepcopy(pin))
    elif change == "bad_hex":
        pin["attempt_id"] = "z" * 32
    elif change == "no_completion":
        pin["completion_digest"] = None
    elif change == "no_resource":
        pin["resource_name"] = None
    elif change == "long_resource":
        pin["resource_name"] = "x" * 129
    elif change == "nested_extra":
        pin["response"] = {}
    else:
        pin["latest_receipt_sequence"] = True
    with pytest.raises(ValidationError):
        GoogleCreatedIds.model_validate(data)


def total_example() -> dict[str, Any]:
    data = example()
    data.update(mode="total_created", provider_posts=2)
    campaign = deepcopy(data["attempts"][0])
    campaign.update(
        step_id="campaign",
        attempt_id="c" * 32,
        fence="c" * 32,
        latest_receipt_id="c" * 32,
        resource_name="customers/1234567890/campaigns/2",
    )
    data["attempts"].append(campaign)
    return data


def test_total_exact_ordered_pair_roundtrips() -> None:
    parsed = GoogleCreatedIds.model_validate(total_example())
    assert GoogleCreatedIds.model_validate_json(parsed.model_dump_json()) == parsed


@pytest.mark.parametrize(
    "change",
    ["order", "attempt_id", "fence", "latest_receipt_id", "null", "posts", "bool_posts", "missing"],
)
def test_total_requires_distinct_complete_exact_pair(change: str) -> None:
    data = total_example()
    if change == "order":
        data["attempts"].reverse()
    elif change in {"attempt_id", "fence", "latest_receipt_id"}:
        data["attempts"][1][change] = data["attempts"][0][change]
    elif change == "null":
        data["attempts"][1]["completion_digest"] = None
    elif change in {"posts", "bool_posts"}:
        data["provider_posts"] = 1 if change == "posts" else True
    else:
        data["attempts"].pop()
    with pytest.raises(ValidationError):
        GoogleCreatedIds.model_validate(data)
