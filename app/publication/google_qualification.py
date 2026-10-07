"""Bounded actual Google read qualification. Tests inject HTTP; runtime remains unavailable."""

from datetime import datetime, timedelta
from time import monotonic
from typing import Any
from uuid import uuid4

from app.executors.google_publication import GooglePublicationHTTP, GooglePublicationUnavailable
from app.publication.contracts import fingerprint
from app.publication.google_compiler import compile_google, materialize_google
from app.publication.provider_contracts import (
    GoogleQualificationEvidence,
    ProviderContext,
    ProviderPublicationReview,
)


def qualify_google(
    review: ProviderPublicationReview,
    context: ProviderContext,
    transport: GooglePublicationHTTP,
    now: datetime,
) -> GoogleQualificationEvidence:
    """Caller must persist evidence only after rechecking DB generation/ownership.

    Network IO happens outside transaction locks. Empty, paginated, duplicated or
    conflicting rows fail closed; no provider raw response is retained or logged.
    """
    review = ProviderPublicationReview.model_validate(review.model_dump())
    request = materialize_google(
        compile_google(review), uuid4().hex, "budget", {}, {}, uuid4().hex, now
    )
    transport._check(request, context, now)
    rows_seen: list[dict[str, Any]] = []
    deadline = monotonic() + min(60, (context.expires_at - now).total_seconds())

    def row(query: str, key: str) -> dict[str, Any]:
        if monotonic() >= deadline:
            raise GooglePublicationUnavailable("google_configuration_deadline_exceeded")
        result = transport._post(request, context, "googleAds:search", {"query": query})
        rows = result.get("results", [])
        if (
            result.get("nextPageToken")
            or not isinstance(rows, list)
            or len(rows) != 1
            or not isinstance(rows[0], dict)
            or not isinstance(rows[0].get(key), dict)
        ):
            raise GooglePublicationUnavailable("google_configuration_unqualified")
        value: dict[str, Any] = rows[0][key]
        rows_seen.append(value)
        return value

    def require(actual: Any, expected: Any) -> None:
        if type(actual) is not type(expected) or actual != expected:
            raise GooglePublicationUnavailable("google_configuration_unqualified")

    scope, f = review.scope, review.configuration
    customer = row(
        "SELECT customer.id, customer.currency_code, customer.time_zone, customer.status "
        "FROM customer LIMIT 2",
        "customer",
    )
    require(str(customer.get("id")), scope.external_advertiser_id)
    require(customer.get("currencyCode"), review.source.definition.currency)
    require(customer.get("timeZone"), f.account_timezone)
    require(customer.get("status"), "ENABLED")
    goal = row(
        "SELECT custom_conversion_goal.resource_name, custom_conversion_goal.status, "
        "custom_conversion_goal.conversion_actions FROM custom_conversion_goal "
        f"WHERE custom_conversion_goal.resource_name = '{f.custom_conversion_goal}' LIMIT 2",
        "customConversionGoal",
    )
    require(goal.get("resourceName"), f.custom_conversion_goal)
    require(goal.get("status"), "ENABLED")
    actions = goal.get("conversionActions")
    if not isinstance(actions, list) or not all(isinstance(v, str) for v in actions):
        raise GooglePublicationUnavailable("google_configuration_unqualified")
    require(sorted(actions), sorted(f.conversion_actions))
    for action in f.conversion_actions:
        actual = row(
            "SELECT conversion_action.resource_name, conversion_action.status, "
            "conversion_action.category, conversion_action.type FROM conversion_action "
            f"WHERE conversion_action.resource_name = '{action}' LIMIT 2",
            "conversionAction",
        )
        require(actual.get("resourceName"), action)
        require(actual.get("status"), "ENABLED")
        require(actual.get("category"), "PURCHASE")
        require(actual.get("type"), "WEBPAGE")
    for country, resource in sorted(f.country_targets.items()):
        actual = row(
            "SELECT geo_target_constant.resource_name, geo_target_constant.country_code, "
            "geo_target_constant.target_type, geo_target_constant.status "
            "FROM geo_target_constant "
            f"WHERE geo_target_constant.resource_name = '{resource}' LIMIT 2",
            "geoTargetConstant",
        )
        require(actual.get("resourceName"), resource)
        require(actual.get("countryCode"), country)
        require(actual.get("targetType"), "Country")
        require(actual.get("status"), "ENABLED")
    for language, resource in sorted(f.language_targets.items()):
        actual = row(
            "SELECT language_constant.resource_name, language_constant.code, "
            "language_constant.targetable FROM language_constant "
            f"WHERE language_constant.resource_name = '{resource}' LIMIT 2",
            "languageConstant",
        )
        require(actual.get("resourceName"), resource)
        require(actual.get("code"), language)
        require(actual.get("targetable"), True)
    return GoogleQualificationEvidence(
        scope=scope,
        binding_digest=review.configuration_binding(),
        observed_at=now,
        expires_at=min(now + timedelta(minutes=5), context.expires_at),
        evidence_digest=fingerprint("google.configuration.readback.v25", {"rows": rows_seen}),
    )
