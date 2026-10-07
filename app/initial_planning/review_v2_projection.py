"""Exact shared native semantics, without inferring qualification or freshness."""

from app.initial_planning.native_budget_contracts import NativeBudgetObservationV1
from app.initial_planning.review_v2_contracts import NativeReviewMatchV1
from app.publication.contracts import fingerprint
from app.publication.optimization_contracts import MetaCurrentState


def native_review_match(
    observation: NativeBudgetObservationV1, current: MetaCurrentState
) -> NativeReviewMatchV1:
    # Revalidate even callers using Pydantic's unchecked model_copy(update=...).
    observation = NativeBudgetObservationV1.model_validate(observation.model_dump())
    current = MetaCurrentState.model_validate(current.model_dump())
    if (
        observation.unsupported_reasons
        or observation.request.target.kind != "campaign"
        or observation.budget_mode != "daily"
        or observation.currency != "USD"
        or observation.currency_exponent != 2
        or not current.complete
        or current.unsupported_features
        or current.target.kind != "campaign"
        or current.target != current.budget_owner.owner
        or current.objective != "OUTCOME_SALES"
        or current.buying_type != "AUCTION"
        or current.lifetime_budget_micros not in (None, 0)
        or current.parent_configured_status != current.configured_status
    ):
        raise ValueError("native_review_profile_unavailable")
    native = observation.model_dump(mode="json")
    qualified = current.model_dump(mode="json")
    native_fields = {
        "scope": native["request"]["scope"],
        "target": native["request"]["target"],
        "budget_owner": native["budget_owner"],
        "currency": native["currency"],
        "currency_exponent": native["currency_exponent"],
        "time_zone": native["time_zone"],
        "amount_micros": native["amount_micros"],
    }
    qualified_fields = {
        "scope": qualified["scope"],
        "target": qualified["target"],
        "budget_owner": qualified["budget_owner"],
        "currency": qualified["money"]["currency"],
        "currency_exponent": qualified["money"]["currency_exponent"],
        "time_zone": qualified["money"]["account_timezone"],
        "amount_micros": qualified["daily_budget_micros"],
    }
    for fields in (native_fields, qualified_fields):
        owner = fields["budget_owner"]
        owner["affected_targets"] = sorted(
            owner["affected_targets"], key=lambda target: (target["kind"], target["external_id"])
        )
    for key in (
        "account_status",
        "configured_status",
        "effective_status",
        "starts_at",
        "ends_at",
        "sharing_enabled",
        "schedule_adjustments_enabled",
        "rebalance_enabled",
        "unaffected_settings_digest",
    ):
        native_fields[key] = native[key]
        qualified_fields[key] = qualified[key]
    if native_fields != qualified_fields:
        raise ValueError("native_review_state_changed")
    return NativeReviewMatchV1(
        native_observation_digest=observation.digest(),
        qualified_state_digest=current.digest(),
        semantic_digest=fingerprint("inlet.native-review-semantics.v1", native_fields),
    )
