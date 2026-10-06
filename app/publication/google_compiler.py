"""Server compiler; all publication fields come from the separately reviewed document."""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.campaign_review.contracts import GoogleSearch
from app.publication.contracts import ResourceRef
from app.publication.provider_contracts import (
    BoundProviderRequest,
    GoogleCreateBudget,
    GoogleCreateCampaignCriterion,
    GoogleCreateExactKeyword,
    GoogleCreatePausedAdGroup,
    GoogleCreatePausedCampaign,
    GoogleCreatePausedResponsiveSearchAd,
    GoogleSetConversionGoal,
    ProviderOperation,
    ProviderPublicationReview,
    ProviderPublishPlan,
    ProviderPublishStep,
    ProviderReceipt,
    operation_refs,
)


def compile_google(review: ProviderPublicationReview) -> ProviderPublishPlan:
    review = ProviderPublicationReview.model_validate(review.model_dump())
    definition, fields = review.source.definition, review.configuration
    content = definition.content
    if not isinstance(content, GoogleSearch):
        raise ValueError("unregistered provider compiler")
    steps: list[ProviderPublishStep] = []

    def add(key: str, operation: ProviderOperation, dependencies: list[str]) -> None:
        steps.append(
            ProviderPublishStep(step_id=key, dependencies=dependencies, operation=operation)
        )

    add("budget", GoogleCreateBudget(amount_micros=fields.daily_budget_micros), [])
    zone = ZoneInfo(fields.account_timezone)
    add(
        "campaign",
        GoogleCreatePausedCampaign(
            name=content.name,
            budget=ResourceRef(step_id="budget"),
            configuration=fields,
            starts_local=definition.starts_at.astimezone(zone).strftime("%Y-%m-%d %H:%M:%S"),
            ends_local=definition.ends_at.astimezone(zone).strftime("%Y-%m-%d %H:%M:%S"),
        ),
        ["budget"],
    )
    add(
        "conversion_goal",
        GoogleSetConversionGoal(
            campaign=ResourceRef(step_id="campaign"),
            custom_conversion_goal=fields.custom_conversion_goal,
        ),
        ["campaign"],
    )
    for index, target in enumerate(
        [*fields.country_targets.values(), *fields.language_targets.values()]
    ):
        add(
            f"target_{index}",
            GoogleCreateCampaignCriterion(campaign=ResourceRef(step_id="campaign"), target=target),
            ["campaign"],
        )
    add(
        "group",
        GoogleCreatePausedAdGroup(
            campaign=ResourceRef(step_id="campaign"),
            name=content.name,
            cpc_bid_micros=fields.max_cpc_micros,
        ),
        [step.step_id for step in steps],
    )
    for index, keyword in enumerate(content.exact_keywords):
        add(
            f"keyword_{index}",
            GoogleCreateExactKeyword(group=ResourceRef(step_id="group"), text=keyword),
            ["group"],
        )
    add(
        "ad",
        GoogleCreatePausedResponsiveSearchAd(group=ResourceRef(step_id="group"), content=content),
        [step.step_id for step in steps],
    )
    return ProviderPublishPlan(review=review, review_digest=review.digest(), steps=steps)


def materialize_google(
    plan: ProviderPublishPlan,
    plan_id: str,
    step_id: str,
    receipts: dict[str, ProviderReceipt],
    requests: dict[str, BoundProviderRequest],
    fence: str,
    now: datetime,
) -> BoundProviderRequest:
    """Receipts must come from the coordinator's immutable archive, never a customer body."""
    plan = ProviderPublishPlan.model_validate(plan.model_dump())
    if compile_google(plan.review) != plan:
        raise ValueError("noncanonical provider plan")
    step = next((value for value in plan.steps if value.step_id == step_id), None)
    if step is None:
        raise ValueError("unknown provider step")
    resources: dict[str, str] = {}
    references = {ref.step_id for ref in operation_refs(step.operation)}
    for dependency in step.dependencies:
        receipt, request = receipts.get(dependency), requests.get(dependency)
        if receipt is None or request is None:
            raise ValueError("verified dependency required")
        receipt = ProviderReceipt.model_validate(receipt.model_dump())
        request = BoundProviderRequest.model_validate(request.model_dump())
        expected_step = next(value for value in plan.steps if value.step_id == dependency)
        if (
            receipt.outcome != "verified_effect"
            or receipt.scope != plan.review.scope
            or receipt.plan_id != plan_id
            or receipt.plan_digest != plan.digest()
            or receipt.step_id != dependency
            or receipt.fence != request.fence
            or receipt.request_digest != request.digest()
            or request.plan_id != plan_id
            or request.plan_digest != plan.digest()
            or request.scope != plan.review.scope
            or request.step != expected_step
            or request.review_digest != plan.review_digest
            or not request.dispatched_at <= receipt.observed_at <= now
        ):
            raise ValueError("stale or foreign provider dependency")
        if dependency in references:
            assert receipt.resource_name is not None
            resources[dependency] = receipt.resource_name
    return BoundProviderRequest(
        plan_id=plan_id,
        plan_digest=plan.digest(),
        review_digest=plan.review_digest,
        scope=plan.review.scope,
        login_customer_id=plan.review.configuration.login_customer_id,
        step=step,
        resources=resources,
        fence=fence,
        dispatched_at=now,
    )
