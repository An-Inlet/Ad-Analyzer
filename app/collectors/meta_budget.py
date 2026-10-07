"""Bounded GET-only native budget collection; no mutation or exposure interfaces."""

import hashlib
import hmac
import json
import re
from collections.abc import Callable
from datetime import datetime, timedelta
from time import monotonic
from typing import Any

import httpx
from pydantic import AwareDatetime, Field, SecretStr

from app.executors.optimization_http import OptimizationUnavailable
from app.executors.social_http import _private_http
from app.initial_planning.contracts import Frozen
from app.initial_planning.native_budget_contracts import (
    NativeBudgetCatalogV1,
    NativeBudgetObservationV1,
    NativeBudgetOptionV1,
    NativeBudgetRequestV1,
)
from app.meta.budget_currency import supported_budget_exponent
from app.meta.budget_snapshot import parse_meta_budget
from app.planning_reporting.contracts import NativeBudgetReadPolicyV1
from app.publication.provider_contracts import Digest


class NativeBudgetUnavailable(RuntimeError):
    """Fixed-code only; credentials/provider payloads never included."""


class NativeBudgetContext(Frozen):
    request_digest: Digest
    access_token: SecretStr = Field(exclude=True, repr=False)
    app_secret: SecretStr | None = Field(exclude=True, repr=False)
    expires_at: AwareDatetime
    label: str = Field(min_length=1, max_length=200)


def native_currency_exponent(currency: str) -> int:
    # Deliberately narrow supported mapping, never an inferred two-decimal default.
    try:
        return supported_budget_exponent(currency)
    except ValueError:
        raise NativeBudgetUnavailable("native_budget_currency_unsupported") from None


class MetaBudgetHTTP:
    def __init__(
        self,
        context: Callable[[NativeBudgetRequestV1, datetime], NativeBudgetContext],
        policy: NativeBudgetReadPolicyV1,
        *,
        transport: httpx.BaseTransport,
        clock: Callable[[], datetime],
    ) -> None:
        self.context, self.policy, self.transport, self.clock = context, policy, transport, clock

    def read(self, request: NativeBudgetRequestV1, now: datetime) -> NativeBudgetCatalogV1:
        start = self.clock()
        if now.tzinfo is None or start < now:
            raise NativeBudgetUnavailable("native_budget_clock_changed")
        deadline = monotonic() + self.policy.total_deadline_seconds
        exponent = native_currency_exponent(request.cohort.currency)
        if not re.fullmatch(r"[0-9]{1,32}", request.scope.external_advertiser_id):
            raise NativeBudgetUnavailable("native_budget_account_invalid")
        original: NativeBudgetContext | None = None

        def current() -> NativeBudgetContext:
            nonlocal original
            at = self.clock()
            if (
                at < start
                or monotonic() >= deadline
                or at >= start + timedelta(seconds=self.policy.observation_lifetime_seconds)
            ):
                raise NativeBudgetUnavailable("native_budget_deadline")
            ctx = self.context(request, at)
            if (
                ctx.request_digest != request.digest()
                or ctx.expires_at <= at
                or not 1 <= len(ctx.access_token.get_secret_value()) <= 16384
            ):
                raise NativeBudgetUnavailable("native_budget_context_changed")
            if original is None:
                original = ctx
            elif ctx != original:
                raise NativeBudgetUnavailable("native_budget_context_changed")
            return ctx

        def get(path: str, params: dict[str, str]) -> dict[str, Any]:
            if not re.fullmatch(r"/v26\.0/[a-zA-Z0-9_/]+", path):
                raise NativeBudgetUnavailable("native_budget_path_invalid")
            ctx = current()
            query = dict(params)
            token = ctx.access_token.get_secret_value()
            if ctx.app_secret is not None:
                query["appsecret_proof"] = hmac.new(
                    ctx.app_secret.get_secret_value().encode(), token.encode(), hashlib.sha256
                ).hexdigest()
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise NativeBudgetUnavailable("native_budget_deadline")
            with client.stream(
                "GET",
                "https://graph.facebook.com" + path,
                params=query,
                headers={"Authorization": "Bearer " + token, "Accept-Encoding": "identity"},
                timeout=min(self.policy.http_timeout_seconds, remaining),
            ) as response:
                if (
                    response.status_code != 200
                    or response.headers.get("Content-Encoding", "identity") != "identity"
                ):
                    raise NativeBudgetUnavailable("native_budget_provider_unavailable")
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 2_000_000 or monotonic() >= deadline:
                        raise NativeBudgetUnavailable("native_budget_response_bound")
                data = json.loads(raw)
            current()  # Fresh original-session/source/goal check after every blocking request.
            if not isinstance(data, dict) or data.get("error"):
                raise NativeBudgetUnavailable("native_budget_provider_unavailable")
            return data

        privacy = _private_http.set(True)
        try:
            with httpx.Client(
                transport=self.transport,
                follow_redirects=False,
                trust_env=False,
                timeout=self.policy.http_timeout_seconds,
            ) as client:
                account = get(
                    "/v26.0/act_" + request.scope.external_advertiser_id,
                    {
                        "fields": "account_id,currency,timezone_name,account_status",
                    },
                )
                if (
                    account.get("account_id") != request.scope.external_advertiser_id
                    or account.get("currency") != request.cohort.currency
                    or account.get("timezone_name") != request.cohort.time_zone
                    or type(account.get("account_status")) is not int
                ):
                    raise NativeBudgetUnavailable("native_budget_account_changed")
                campaign = get(
                    "/v26.0/" + request.target.campaign_id,
                    {
                        "fields": "id,account_id,configured_status,effective_status,daily_budget,"
                        "lifetime_budget,is_budget_schedule_enabled,start_time,stop_time,objective,"
                        "buying_type,is_adset_budget_sharing_enabled,budget_rebalance_flag",
                    },
                )
                children: list[dict[str, Any]] = []
                seen: set[str] = set()
                cursor: str | None = None
                for _ in range(self.policy.maximum_pages):
                    params = {
                        "fields": "id,account_id,campaign_id",
                        "limit": "100",
                        "effective_status": json.dumps(
                            [
                                "ACTIVE",
                                "PAUSED",
                                "ARCHIVED",
                                "DELETED",
                                "IN_PROCESS",
                                "WITH_ISSUES",
                                "CAMPAIGN_PAUSED",
                            ]
                        ),
                    }
                    if cursor is not None:
                        params["after"] = cursor
                    page = get("/v26.0/" + request.target.campaign_id + "/adsets", params)
                    rows, paging = page.get("data"), page.get("paging", {})
                    if (
                        not isinstance(rows, list)
                        or any(not isinstance(row, dict) for row in rows)
                        or not isinstance(paging, dict)
                    ):
                        raise NativeBudgetUnavailable("native_budget_topology_unavailable")
                    children.extend(rows)
                    if len(children) + 1 > self.policy.maximum_targets:
                        raise NativeBudgetUnavailable("native_budget_topology_capacity")
                    if not paging.get("next"):
                        break
                    cursors = paging.get("cursors")
                    cursor = cursors.get("after") if isinstance(cursors, dict) else None
                    if (
                        not isinstance(cursor, str)
                        or not 1 <= len(cursor) <= 1024
                        or cursor in seen
                    ):
                        raise NativeBudgetUnavailable("native_budget_topology_cursor")
                    seen.add(cursor)
                else:
                    raise NativeBudgetUnavailable("native_budget_topology_capacity")
                snapshot = parse_meta_budget(
                    request.scope, request.target, exponent, account, campaign, campaign, children
                )
                reasons = list(snapshot.unsupported_features)
                for flag, reason in (
                    (snapshot.sharing_enabled, "budget_sharing_enabled"),
                    (snapshot.schedule_adjustments_enabled, "budget_schedule_enabled"),
                    (snapshot.rebalance_enabled, "budget_rebalance_enabled"),
                ):
                    if flag is True:
                        reasons.append(reason)
                budgets = [
                    (kind, amount)
                    for kind, amount in (
                        ("daily", snapshot.daily_budget_micros),
                        ("lifetime", snapshot.lifetime_budget_micros),
                    )
                    if amount is not None and amount > 0
                ]
                if len(budgets) != 1:
                    reasons.append("budget_mode_unavailable")
                ctx = current()
                end = self.clock()
                expires = min(
                    start + timedelta(seconds=self.policy.observation_lifetime_seconds),
                    ctx.expires_at,
                )
                if end < start or end >= expires or monotonic() >= deadline:
                    raise NativeBudgetUnavailable("native_budget_deadline")
                observation = NativeBudgetObservationV1.model_validate(
                    {
                        "request": request.model_dump(),
                        "budget_owner": snapshot.budget_owner.model_dump(),
                        "currency": request.cohort.currency,
                        "currency_exponent": exponent,
                        "time_zone": request.cohort.time_zone,
                        "budget_mode": budgets[0][0] if len(budgets) == 1 else None,
                        "amount_micros": budgets[0][1] if len(budgets) == 1 else None,
                        **snapshot.model_dump(
                            include={
                                "account_status",
                                "configured_status",
                                "effective_status",
                                "starts_at",
                                "ends_at",
                                "sharing_enabled",
                                "schedule_adjustments_enabled",
                                "rebalance_enabled",
                                "unaffected_settings_digest",
                            }
                        ),
                        "unsupported_reasons": reasons,
                        "observation_started_at": start,
                        "observed_at": end,
                        "expires_at": expires,
                    }
                )
                return NativeBudgetCatalogV1(
                    request=request,
                    observed_at=end,
                    expires_at=expires,
                    options=()
                    if reasons
                    else (NativeBudgetOptionV1(label=ctx.label, observation=observation),),
                )
        except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError, OptimizationUnavailable):
            raise NativeBudgetUnavailable("native_budget_unavailable") from None
        finally:
            _private_http.reset(privacy)
